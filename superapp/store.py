"""Super App — alohida ma'lumotlar bazasi (superapp.db).

⚠️ Botning bot_database.db siga TEGMAYDI. Bu yerda faqat yangi modullar
ma'lumoti: ballar, hold'lar, generatsiya tarixi, uslub xotirasi.

Nega alohida fayl: slot sikli har 0.5s da bot_database.db ga yozadi. Agar
infografika yozuvlari ham o'sha faylga tushsa, sqlite yozuv qulfi sikni
cho'zishi va band qilishni kechiktirishi mumkin edi.
"""

import time
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

from superapp.config import SUPERAPP_DB


@asynccontextmanager
async def _db():
    """Ulanish ochish/yopish — bitta joyda.

    ⚠️ `async with await aiosqlite.connect(...)` YOZMANG: `await` ulanish
    thread'ini ishga tushiradi, keyin `__aenter__` uni QAYTA ishga tushirmoqchi
    bo'ladi va "threads can only be started once" xatosi chiqadi.
    """
    c = await aiosqlite.connect(SUPERAPP_DB)
    c.row_factory = aiosqlite.Row
    await c.execute("PRAGMA journal_mode=WAL")
    # Boshqa yozuvchi bo'lsa xato o'rniga kutamiz (parallel so'rovlar uchun)
    await c.execute("PRAGMA busy_timeout=5000")
    try:
        yield c
    finally:
        await c.close()


async def init() -> None:
    """Jadvallarni yaratish (idempotent)."""
    async with _db() as c:
        # Ball balansi (1 kredit -> BALLS_PER_CREDIT ball)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                telegram_id       INTEGER PRIMARY KEY,
                balls             INTEGER NOT NULL DEFAULT 0,
                free_retries_used INTEGER NOT NULL DEFAULT 0,
                updated_at        TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Ball harakati tarixi (audit — pul masalasi, izsiz qolmasin)
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                delta       INTEGER NOT NULL,
                reason      TEXT NOT NULL,
                ref         TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        await c.execute(
            "CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger(telegram_id)")

        # Hold — generatsiya boshlanganda ushlab turilgan ballar.
        # Asinxron generatsiya uchun MAJBURIY: natija 20-60s dan keyin keladi,
        # shu orada mijoz balansni boshqa joyga sarflab yubormasligi kerak.
        await c.execute("""
            CREATE TABLE IF NOT EXISTS holds (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                balls       INTEGER NOT NULL,
                kind        TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'held',
                created_at  REAL NOT NULL,
                resolved_at REAL
            )
        """)
        await c.execute(
            "CREATE INDEX IF NOT EXISTS idx_holds_open ON holds(status, created_at)")

        # Generatsiyalar
        await c.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id  INTEGER NOT NULL,
                action_id    TEXT UNIQUE,
                hold_id      INTEGER,
                kind         TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                product_name TEXT,
                category_id  TEXT,
                concept_id   TEXT,
                result_url   TEXT,
                error        TEXT,
                created_at   REAL NOT NULL,
                completed_at REAL
            )
        """)
        await c.execute(
            "CREATE INDEX IF NOT EXISTS idx_gen_user ON generations(telegram_id, id DESC)")
        await c.execute(
            "CREATE INDEX IF NOT EXISTS idx_gen_open ON generations(status)")

        # Migratsiyalar — mavjud bazaga yangi ustunlar (asosiy loyihadagi
        # uslub bilan bir xil: har biri alohida try, borini o'tkazib yuboradi).
        for stmt in (
            "ALTER TABLE generations ADD COLUMN wishes TEXT",
            "ALTER TABLE generations ADD COLUMN description TEXT",
            "ALTER TABLE generations ADD COLUMN parent_id INTEGER",
            "ALTER TABLE generations ADD COLUMN is_free INTEGER DEFAULT 0",
        ):
            try:
                await c.execute(stmt)
            except Exception:
                pass          # ustun allaqachon bor

        # USLUB XOTIRASI — bizning asosiy ustunligimiz.
        # Mijozga yoqqan kartochka `design_reference` bo'lib saqlanadi va
        # keyingi hamma kartochka shu uslubda chiqadi (bir do'kon = bir uslub).
        await c.execute("""
            CREATE TABLE IF NOT EXISTS styles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                name        TEXT,
                source_url  TEXT,
                upload_id   TEXT,
                creativity  REAL DEFAULT 0.3,
                is_default  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        await c.execute(
            "CREATE INDEX IF NOT EXISTS idx_styles_user ON styles(telegram_id)")

        await c.commit()


# ─────────────────────────── Balans ───────────────────────────

async def get_balls(telegram_id: int) -> int:
    async with _db() as c:
        cur = await c.execute(
            "SELECT balls FROM balances WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        return int(row["balls"]) if row else 0


async def add_balls(telegram_id: int, n: int, reason: str,
                    ref: Optional[str] = None) -> int:
    """Ball qo'shish/ayirish + audit yozuvi. Yangi balansni qaytaradi.

    ⚠️ Balans hech qachon manfiy bo'lmaydi (max(0, ...)).
    """
    async with _db() as c:
        await c.execute(
            "INSERT OR IGNORE INTO balances(telegram_id, balls) VALUES(?, 0)",
            (telegram_id,))
        await c.execute(
            "UPDATE balances SET balls = MAX(0, balls + ?),"
            " updated_at = datetime('now','localtime') WHERE telegram_id=?",
            (n, telegram_id))
        await c.execute(
            "INSERT INTO ledger(telegram_id, delta, reason, ref) VALUES(?,?,?,?)",
            (telegram_id, n, reason, ref))
        cur = await c.execute(
            "SELECT balls FROM balances WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        await c.commit()
        return int(row["balls"]) if row else 0


# ─────────────────────────── Hold ───────────────────────────

async def create_hold(telegram_id: int, balls: int, kind: str) -> Optional[int]:
    """Ballarni ushlab turish (balansdan yechib, hold'ga o'tkazish).

    Balans yetmasa None qaytaradi — chaqiruvchi 402 beradi.
    Yechish va hold yaratish BITTA tranzaksiyada (yarim holat bo'lmasin).
    """
    async with _db() as c:
        try:
            await c.execute("BEGIN IMMEDIATE")
            cur = await c.execute(
                "SELECT balls FROM balances WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            have = int(row["balls"]) if row else 0
            if have < balls:
                await c.rollback()
                return None
            await c.execute(
                "UPDATE balances SET balls = balls - ?,"
                " updated_at = datetime('now','localtime') WHERE telegram_id=?",
                (balls, telegram_id))
            cur = await c.execute(
                "INSERT INTO holds(telegram_id, balls, kind, created_at)"
                " VALUES(?,?,?,?)", (telegram_id, balls, kind, time.time()))
            hold_id = cur.lastrowid
            await c.execute(
                "INSERT INTO ledger(telegram_id, delta, reason, ref) VALUES(?,?,?,?)",
                (telegram_id, -balls, f"hold:{kind}", str(hold_id)))
            await c.commit()
            return hold_id
        except Exception:
            await c.rollback()
            raise


async def resolve_hold(hold_id: int, ok: bool) -> bool:
    """Hold'ni yakunlash: ok=True -> sarflandi, ok=False -> ballar QAYTARILADI.

    Idempotent: allaqachon yakunlangan hold ikkinchi marta ta'sir qilmaydi
    (webhook + poll ikkalasi ham kelishi mumkin — ikki marta qaytarib
    yubormaslik uchun bu SHART).
    """
    async with _db() as c:
        try:
            await c.execute("BEGIN IMMEDIATE")
            cur = await c.execute(
                "SELECT telegram_id, balls, status FROM holds WHERE id=?", (hold_id,))
            row = await cur.fetchone()
            if row is None or row["status"] != "held":
                await c.rollback()
                return False          # yo'q yoki allaqachon yakunlangan
            new_status = "committed" if ok else "refunded"
            await c.execute(
                "UPDATE holds SET status=?, resolved_at=? WHERE id=?",
                (new_status, time.time(), hold_id))
            if not ok:
                await c.execute(
                    "UPDATE balances SET balls = balls + ?,"
                    " updated_at = datetime('now','localtime') WHERE telegram_id=?",
                    (row["balls"], row["telegram_id"]))
                await c.execute(
                    "INSERT INTO ledger(telegram_id, delta, reason, ref)"
                    " VALUES(?,?,?,?)",
                    (row["telegram_id"], row["balls"], "refund", str(hold_id)))
            await c.commit()
            return True
        except Exception:
            await c.rollback()
            raise


async def expire_holds(ttl: float) -> int:
    """Osilib qolgan hold'larni qaytarish (Aidentika javob bermay qolsa).

    Mijozning puli hech qachon 'ushlangan' holatda abadiy qolmasligi kerak.
    """
    cutoff = time.time() - ttl
    async with _db() as c:
        cur = await c.execute(
            "SELECT id FROM holds WHERE status='held' AND created_at < ?", (cutoff,))
        ids = [r["id"] for r in await cur.fetchall()]
    n = 0
    for hid in ids:
        if await resolve_hold(hid, ok=False):
            n += 1
    return n


# ─────────────────────── Generatsiyalar ───────────────────────

async def create_generation(telegram_id: int, kind: str, hold_id: Optional[int],
                            product_name: str = "", category_id: str = "",
                            concept_id: str = "", wishes: str = "",
                            description: str = "", parent_id: Optional[int] = None,
                            is_free: bool = False) -> int:
    async with _db() as c:
        cur = await c.execute(
            "INSERT INTO generations(telegram_id, hold_id, kind, product_name,"
            " category_id, concept_id, wishes, description, parent_id, is_free,"
            " created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (telegram_id, hold_id, kind, product_name, category_id, concept_id,
             wishes, description, parent_id, 1 if is_free else 0, time.time()))
        await c.commit()
        return cur.lastrowid


# ─────────────── Bepul qayta generatsiyalar ───────────────

async def take_free_retry(telegram_id: int, limit: int) -> bool:
    """Bepul qayta generatsiyani ATOMIK olish.

    Shartli UPDATE: limitdan oshsa qatorga tegmaydi va False qaytaradi.
    Ikki barobar bosilganda ikkita bepul berib yubormaslik uchun shu shart.
    """
    async with _db() as c:
        await c.execute(
            "INSERT OR IGNORE INTO balances(telegram_id, balls) VALUES(?, 0)",
            (telegram_id,))
        cur = await c.execute(
            "UPDATE balances SET free_retries_used = free_retries_used + 1"
            " WHERE telegram_id = ? AND free_retries_used < ?",
            (telegram_id, limit))
        await c.commit()
        return cur.rowcount > 0


async def free_retries_left(telegram_id: int, limit: int) -> int:
    async with _db() as c:
        cur = await c.execute(
            "SELECT free_retries_used FROM balances WHERE telegram_id=?",
            (telegram_id,))
        row = await cur.fetchone()
        used = int(row["free_retries_used"]) if row else 0
        return max(0, limit - used)


async def attach_action(gen_id: int, action_id: str) -> None:
    async with _db() as c:
        await c.execute("UPDATE generations SET action_id=? WHERE id=?",
                        (str(action_id), gen_id))
        await c.commit()


async def finish_generation(gen_id: int, status: str, result_url: str = "",
                            error: str = "") -> None:
    async with _db() as c:
        await c.execute(
            "UPDATE generations SET status=?, result_url=?, error=?,"
            " completed_at=? WHERE id=?",
            (status, result_url, error, time.time(), gen_id))
        await c.commit()


async def get_generation(gen_id: int) -> Optional[dict]:
    async with _db() as c:
        cur = await c.execute("SELECT * FROM generations WHERE id=?", (gen_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_generation_by_action(action_id: str) -> Optional[dict]:
    async with _db() as c:
        cur = await c.execute("SELECT * FROM generations WHERE action_id=?",
                              (str(action_id),))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_generations(telegram_id: int, limit: int = 30) -> list:
    async with _db() as c:
        cur = await c.execute(
            "SELECT * FROM generations WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit))
        return [dict(r) for r in await cur.fetchall()]


async def count_open_jobs(telegram_id: int) -> int:
    async with _db() as c:
        cur = await c.execute(
            "SELECT COUNT(*) n FROM generations WHERE telegram_id=?"
            " AND status IN ('pending','running')", (telegram_id,))
        row = await cur.fetchone()
        return int(row["n"])


async def list_open_generations() -> list:
    """Tugallanmagan generatsiyalar (poll qiluvchi uchun)."""
    async with _db() as c:
        cur = await c.execute(
            "SELECT * FROM generations WHERE status IN ('pending','running')"
            " AND action_id IS NOT NULL ORDER BY id")
        return [dict(r) for r in await cur.fetchall()]


# ───────────────────────── Uslub ─────────────────────────

async def save_style(telegram_id: int, source_url: str, name: str = "",
                     creativity: float = 0.3, make_default: bool = True) -> int:
    async with _db() as c:
        if make_default:
            await c.execute(
                "UPDATE styles SET is_default=0 WHERE telegram_id=?", (telegram_id,))
        cur = await c.execute(
            "INSERT INTO styles(telegram_id, name, source_url, creativity, is_default)"
            " VALUES(?,?,?,?,?)",
            (telegram_id, name, source_url, creativity, 1 if make_default else 0))
        await c.commit()
        return cur.lastrowid


async def get_default_style(telegram_id: int) -> Optional[dict]:
    async with _db() as c:
        cur = await c.execute(
            "SELECT * FROM styles WHERE telegram_id=? AND is_default=1"
            " ORDER BY id DESC LIMIT 1", (telegram_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_styles(telegram_id: int) -> list:
    async with _db() as c:
        cur = await c.execute(
            "SELECT * FROM styles WHERE telegram_id=? ORDER BY is_default DESC, id DESC",
            (telegram_id,))
        return [dict(r) for r in await cur.fetchall()]
