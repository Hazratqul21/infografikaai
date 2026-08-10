"""
Uzum Slot Bot — Ma'lumotlar Bazasi (SQLite + aiosqlite)

Foydalanuvchilar, vazifalar, to'lovlar va loglarni boshqaradi.
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
from config import DB_PATH, logger


async def init_db() -> None:
    """Ma'lumotlar bazasini yaratish va jadvallarni tayyorlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER UNIQUE NOT NULL,
                full_name       TEXT,
                username        TEXT,
                phone           TEXT,
                api_token       TEXT,
                is_active       INTEGER DEFAULT 1,
                subscription    TEXT DEFAULT 'free',
                created_at      TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at      TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Slot vazifalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS slot_tasks (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id         INTEGER NOT NULL,
                shop_id             TEXT NOT NULL,
                nakladnoy_number    TEXT NOT NULL,
                warehouse           TEXT,
                preferred_date      TEXT,
                time_preference     TEXT DEFAULT 'any',
                status              TEXT DEFAULT 'waiting',
                slot_info           TEXT,
                attempts            INTEGER DEFAULT 0,
                last_check          TEXT,
                created_at          TEXT DEFAULT (datetime('now', 'localtime')),
                booked_at           TEXT,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        """)

        # Tekshirish loglari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     INTEGER NOT NULL,
                status      TEXT,
                response    TEXT,
                created_at  TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (task_id) REFERENCES slot_tasks(id)
            )
        """)

        # Indekslar (tezlik uchun)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON slot_tasks(status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_telegram
            ON slot_tasks(telegram_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_task
            ON check_logs(task_id)
        """)

        # To'lovlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                order_id        TEXT UNIQUE NOT NULL,
                amount          INTEGER NOT NULL,
                status          TEXT DEFAULT 'pending',
                created_at      TEXT DEFAULT (datetime('now', 'localtime')),
                confirmed_at    TEXT
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_telegram
            ON payments(telegram_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_order
            ON payments(order_id)
        """)

        # Sozlamalar jadvali (admin boshqaruvi uchun)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Promo kodlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        TEXT UNIQUE NOT NULL,
                days        INTEGER NOT NULL DEFAULT 30,
                max_uses    INTEGER DEFAULT 1,
                used_count  INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Standart sozlamalarni qo'shish (agar mavjud bo'lmasa)
        default_settings = [
            ("subscription_price", "50000"),
            ("payme_test_mode", "true"),
        ]
        for key, value in default_settings:
            await db.execute(
                """
                INSERT OR IGNORE INTO settings (key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )

        # Yangi ustunlarni qo'shish (agar mavjud bazada yo'q bo'lsa)
        try:
            await db.execute(
                "ALTER TABLE slot_tasks ADD COLUMN time_preference TEXT DEFAULT 'any'"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud

        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN subscription TEXT DEFAULT 'free'"
            )
        except Exception:
            pass

        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN subscription_expires_at TEXT"
            )
        except Exception:
            pass

        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN shop_id TEXT"
            )
        except Exception:
            pass

        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN shop_name TEXT"
            )
        except Exception:
            pass

        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN shop_verified INTEGER DEFAULT 0"
            )
        except Exception:
            pass

        try:
            await db.execute(
                "ALTER TABLE slot_tasks ADD COLUMN target_date TEXT"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud

        # Nakladnoyning user ko'radigan raqami (invoiceNumber, 13 xonali).
        # nakladnoy_number ichki `id` (API uchun) bo'lib qoladi; bu esa
        # xabar/ro'yxatlarda ko'rsatiladi. Eski yozuvlarda NULL — fallback ishlaydi.
        try:
            await db.execute(
                "ALTER TABLE slot_tasks ADD COLUMN invoice_display TEXT"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud

        # Vazifa "error" bo'lganda sababi (admin panelда ko'rsatiladi)
        try:
            await db.execute(
                "ALTER TABLE slot_tasks ADD COLUMN error_reason TEXT"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud

        # KREDIT QAYTARISH: vazifa slot OLMASDAN tugasa 1 kredit qaytariladi.
        # refunded=1 -> allaqachon qaytarilgan (ikki marta qaytarilmasin).
        try:
            await db.execute(
                "ALTER TABLE slot_tasks ADD COLUMN refunded INTEGER DEFAULT 0"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud

        # Kredit tizimi: 1 kredit = 1 nakladnoy. Yangi user 5 bepul kredit.
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 5"
            )
        except Exception:
            pass
        try:
            await db.execute(
                "ALTER TABLE payments ADD COLUMN credits INTEGER DEFAULT 0"
            )
        except Exception:
            pass

        # Ko'p do'kon: bitta user bir nechta do'kon ulashi mumkin
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_shops (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id  INTEGER NOT NULL,
                shop_id      TEXT NOT NULL,
                shop_name    TEXT,
                created_at   TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(telegram_id, shop_id)
            )
        """)
        # Eski (bitta) shop_id larni user_shops ga ko'chirish (bir martalik)
        try:
            await db.execute("""
                INSERT OR IGNORE INTO user_shops (telegram_id, shop_id, shop_name)
                SELECT telegram_id, shop_id, shop_name FROM users
                WHERE shop_id IS NOT NULL AND shop_id != ''
            """)
        except Exception:
            pass

        # ── CHEAT HIMOYASI: bepul kreditni DO'KONga bog'lash ──
        # Bepul kredit endi Telegram ID ga emas, DO'KONga bog'lanadi:
        #   - har user faqat BIR marta (birinchi do'koni ulanganda) oladi
        #   - har do'kon faqat BIR marta bepul kredit "beradi" (abadiy qayd)
        # Shu bilan yangi akkaunt ochib o'sha do'konni qayta qo'shib bepul
        # kredit farm qilish imkonsiz bo'ladi.
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN free_credit_taken INTEGER DEFAULT 0"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud
        await db.execute("""
            CREATE TABLE IF NOT EXISTS free_credit_shops (
                shop_id      TEXT PRIMARY KEY,
                telegram_id  INTEGER,
                granted_at   TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # Bir martalik migratsiya (flag bilan himoyalangan — faqat BIR marta):
        # mavjud userlar "sovg'a olgan", ulangan do'konlar "sovg'a berilgan" deb
        # belgilanadi (krediti O'ZGARMAYDI). Eski do'konlar qayta farm qilinmaydi.
        async with db.execute(
            "SELECT 1 FROM settings WHERE key = 'fc_bind_migration_v1'"
        ) as _c:
            _done = await _c.fetchone()
        if not _done:
            try:
                await db.execute("UPDATE users SET free_credit_taken = 1")
                await db.execute("""
                    INSERT OR IGNORE INTO free_credit_shops (shop_id, telegram_id)
                    SELECT shop_id, telegram_id FROM user_shops
                    WHERE shop_id IS NOT NULL AND shop_id != ''
                """)
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) "
                    "VALUES ('fc_bind_migration_v1', '1')"
                )
                logger.info("🛡 Bepul kredit cheat-himoya migratsiyasi bajarildi")
            except Exception as _e:
                logger.error("fc migratsiya xatosi: %s", _e)

        # ── DAROMAD ANIQLIGI: test to'lovlar + doim-chiqariladigan userlar ──
        # is_test=1 -> to'lov daromad hisobiga KIRMAYDI (test/sherik).
        try:
            await db.execute(
                "ALTER TABLE payments ADD COLUMN is_test INTEGER DEFAULT 0"
            )
        except Exception:
            pass  # Ustun allaqachon mavjud
        # Bir martalik (flag): hozirgi barcha tasdiqlangan to'lovlar TEST (real pul
        # kelmagan — admin test uchun tasdiqlagan), daromad 0 dan boshlanadi.
        # Doim-chiqariladigan userlar (o'zi + sherik) settings'ga yoziladi.
        async with db.execute(
            "SELECT 1 FROM settings WHERE key = 'revenue_test_migration_v1'"
        ) as _c:
            _rdone = await _c.fetchone()
        if not _rdone:
            try:
                await db.execute(
                    "UPDATE payments SET is_test = 1 WHERE status = 'confirmed'"
                )
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) "
                    "VALUES ('revenue_excluded_ids', '234413715,5845782796')"
                )
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) "
                    "VALUES ('revenue_test_migration_v1', '1')"
                )
                logger.info("💵 Daromad-aniqlik migratsiyasi: hozirgi to'lovlar test deb belgilandi")
            except Exception as _e:
                logger.error("revenue migratsiya xatosi: %s", _e)

        # ── KO'P AKKAUNT (SHARDING): do'kon → akkaunt xaritasi ──
        # Har do'kon qaysi bot-akkaunti orqali tekshiriladi/band qilinadi.
        # Xaritada yo'q do'kon = akkaunt "1" (backward-compat). Mavjud barcha
        # do'konlar bir martalik "1" ga biriktiriladi (ular #1 da Менеджер).
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_account (
                shop_id     TEXT PRIMARY KEY,
                account_id  TEXT NOT NULL DEFAULT '1',
                assigned_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        async with db.execute(
            "SELECT 1 FROM settings WHERE key = 'shop_account_migration_v1'"
        ) as _c:
            _sdone = await _c.fetchone()
        if not _sdone:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO shop_account (shop_id, account_id)
                    SELECT DISTINCT shop_id, '1' FROM user_shops
                    WHERE shop_id IS NOT NULL AND shop_id != ''
                """)
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) "
                    "VALUES ('shop_account_migration_v1', '1')"
                )
                logger.info("🔀 Sharding migratsiyasi: mavjud do'konlar akkaunt #1 ga biriktirildi")
            except Exception as _e:
                logger.error("shard migratsiya xatosi: %s", _e)

        # ── FOYDALANUVCHI → bot-akkaunt (klient BITTA raqam ko'radi) ──
        # Marshrut do'kon bo'yicha EMAS, USER bo'yicha: bitta klient bitta
        # raqamni Менеджер qiladi va uning BARCHA do'konlari shu raqam orqali
        # ishlanadi. Do'kon ulagan (eski) userlar #1 da qoladi — ular 2055 ni
        # allaqachon qo'shgan. Faqat /start bosib do'kon ulamaganlar yangi
        # raqamlarga taqsimlanadi.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_account (
                telegram_id INTEGER PRIMARY KEY,
                account_id  TEXT NOT NULL DEFAULT '1',
                assigned_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        async with db.execute(
            "SELECT 1 FROM settings WHERE key = 'user_account_migration_v1'"
        ) as _c:
            _udone = await _c.fetchone()
        if not _udone:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO user_account (telegram_id, account_id)
                    SELECT DISTINCT telegram_id, '1' FROM user_shops
                    WHERE telegram_id IS NOT NULL
                """)
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) "
                    "VALUES ('user_account_migration_v1', '1')"
                )
                logger.info(
                    "🔀 User-sharding migratsiyasi: do'kon ulagan userlar akkaunt #1 ga biriktirildi")
            except Exception as _e:
                logger.error("user-shard migratsiya xatosi: %s", _e)

        await db.commit()
        logger.info("Ma'lumotlar bazasi tayyor ✅")


# ═══════════════════════════════════════════════════════════════
#  KO'P AKKAUNT (SHARDING): do'kon → bot-akkaunt
# ═══════════════════════════════════════════════════════════════

async def get_account_for_user(telegram_id: int) -> Optional[str]:
    """Foydalanuvchi qaysi bot-akkauntiga biriktirilgan. Biriktirilmagan -> None.

    Eslatma: do'kon ulagan (user_shops'da bor) userlar migratsiyada '1' ga
    yozilgan. Migratsiyadan keyin ulaganlar uchun zaxira tekshiruv ham bor.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id FROM user_account WHERE telegram_id = ?",
            (int(telegram_id),),
        ) as c:
            row = await c.fetchone()
        if row and row[0]:
            return str(row[0])
        # Zaxira: do'koni bor, lekin xaritada yo'q -> eski user, #1
        async with db.execute(
            "SELECT 1 FROM user_shops WHERE telegram_id = ? LIMIT 1",
            (int(telegram_id),),
        ) as c:
            if await c.fetchone():
                return "1"
    return None


async def set_account_for_user(telegram_id: int, account_id: str) -> None:
    """Foydalanuvchini akkauntga biriktirish (mavjud bo'lsa yangilaydi)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_account (telegram_id, account_id) VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET account_id = excluded.account_id
            """,
            (int(telegram_id), str(account_id)),
        )
        await db.commit()


async def resolve_account_for_shop(shop_id: str) -> str:
    """Do'kon qaysi akkaunt orqali ishlanishi — ISHONCHLI aniqlash.

    Tartib:
      1) shop_account xaritasi (onboarding'da biriktirilgan)
      2) xaritada yo'q bo'lsa — DO'KON EGASINING akkaunti (klient qaysi raqamni
         xodim qilgan bo'lsa, o'sha). Bu MUHIM: vazifa yaratishda Do'kon ID
         qo'lda kiritilsa do'kon xaritaga tushmay qolardi — natijada 2055 bilan
         tekshirilib, 2829 klientida "Ruxsat yo'q" chiqishi mumkin edi.
      3) hech biri bo'lmasa — '1' (eski xatti-harakat)
    """
    sid = str(shop_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id FROM shop_account WHERE shop_id = ?", (sid,)
        ) as c:
            row = await c.fetchone()
        if row and row[0]:
            return str(row[0])
        async with db.execute(
            """
            SELECT ua.account_id FROM user_shops us
            JOIN user_account ua ON ua.telegram_id = us.telegram_id
            WHERE us.shop_id = ? AND ua.account_id IS NOT NULL
            ORDER BY us.id LIMIT 1
            """,
            (sid,),
        ) as c:
            row = await c.fetchone()
        if row and row[0]:
            return str(row[0])
    return "1"


async def get_account_user_counts() -> dict:
    """Har akkauntga biriktirilgan FOYDALANUVCHI soni (yukni bo'lish uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id, COUNT(*) FROM user_account GROUP BY account_id"
        ) as c:
            rows = await c.fetchall()
    return {r[0]: r[1] for r in rows}


async def is_known_shop(shop_id: str) -> bool:
    """Do'kon tizimda ILGARI ko'rilganmi (shop_account yoki user_shops da)?

    MUHIM (yukni bo'lish): faqat HECH QACHON ko'rilmagan do'kon yangi akkauntga
    yo'naltiriladi. Allaqachon ulangan do'konlar (klient akkaunt #1 ni Менеджер
    qilib qo'ygan) o'z akkauntida qoladi — klient QAYTA onboarding qilmaydi.
    """
    sid = str(shop_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM shop_account WHERE shop_id = ? "
            "UNION ALL SELECT 1 FROM user_shops WHERE shop_id = ? LIMIT 1",
            (sid, sid),
        ) as c:
            return (await c.fetchone()) is not None


async def get_account_for_shop(shop_id: str) -> str:
    """Do'kon qaysi bot-akkaunti orqali ishlanadi. Xaritada yo'q -> '1'."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id FROM shop_account WHERE shop_id = ?", (str(shop_id),)
        ) as c:
            row = await c.fetchone()
    return row[0] if row and row[0] else "1"


async def assign_shop_account(shop_id: str, account_id: str) -> None:
    """Do'konni akkauntga biriktirish (mavjud bo'lsa yangilaydi)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO shop_account (shop_id, account_id) VALUES (?, ?)
            ON CONFLICT(shop_id) DO UPDATE SET account_id = excluded.account_id
            """,
            (str(shop_id), str(account_id)),
        )
        await db.commit()


async def get_account_shop_counts() -> dict:
    """Har akkauntga biriktirilgan do'kon soni (yukni bo'lish uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id, COUNT(*) FROM shop_account GROUP BY account_id"
        ) as c:
            rows = await c.fetchall()
    return {r[0]: r[1] for r in rows}


async def get_shops_by_account() -> dict:
    """account_id -> [shop_id, ...] (startup/monitoring uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id, shop_id FROM shop_account"
        ) as c:
            rows = await c.fetchall()
    out: dict = {}
    for acc, shop in rows:
        out.setdefault(acc, []).append(shop)
    return out


# ═══════════════════════════════════════════════════════════════
#  KO'P DO'KON (user_shops)
# ═══════════════════════════════════════════════════════════════

async def add_user_shop(telegram_id: int, shop_id: str,
                        shop_name: Optional[str] = None) -> None:
    """Foydalanuvchiga do'kon qo'shish (takror bo'lsa e'tiborsiz)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_shops (telegram_id, shop_id, shop_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, shop_id) DO UPDATE SET
                shop_name = COALESCE(excluded.shop_name, user_shops.shop_name)
            """,
            (telegram_id, str(shop_id), shop_name),
        )
        await db.commit()


async def get_user_shops(telegram_id: int) -> List[dict]:
    """Foydalanuvchining barcha do'konlari."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_shops WHERE telegram_id = ? ORDER BY id",
            (telegram_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def remove_user_shop(telegram_id: int, shop_id: str) -> bool:
    """Do'konni o'chirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM user_shops WHERE telegram_id = ? AND shop_id = ?",
            (telegram_id, str(shop_id)),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_shop_owner(shop_id: str) -> Optional[dict]:
    """Do'kon kimga tegishli (birinchi qo'shgan user). Yo'q bo'lsa None.

    {"telegram_id", "username", "full_name"} qaytaradi.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT us.telegram_id AS telegram_id, u.username AS username,
                   u.full_name AS full_name
            FROM user_shops us
            LEFT JOIN users u ON us.telegram_id = u.telegram_id
            WHERE us.shop_id = ?
            ORDER BY us.id ASC
            LIMIT 1
            """,
            (str(shop_id),),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def cancel_tasks_for_shop(telegram_id: int, shop_id: str) -> int:
    """Do'kon o'chirilganda — o'sha do'konning faol vazifalarini bekor qilish.

    Har bir bekor qilingan vazifa uchun 1 kredit QAYTARILADI.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM slot_tasks WHERE telegram_id = ? AND shop_id = ? "
            "AND status IN ('waiting', 'checking')",
            (telegram_id, str(shop_id)),
        ) as c:
            ids = [r["id"] for r in await c.fetchall()]
        cur = await db.execute(
            "UPDATE slot_tasks SET status = 'cancelled' "
            "WHERE telegram_id = ? AND shop_id = ? "
            "AND status IN ('waiting', 'checking')",
            (telegram_id, str(shop_id)),
        )
        await db.commit()
        n = cur.rowcount
    for tid in ids:
        try:
            await refund_task_credit(tid)
        except Exception as e:
            logger.error("Kredit qaytarishda xato (task=%s): %s", tid, e)
    return n


async def user_owns_shop(telegram_id: int, shop_id: str) -> bool:
    """Do'kon shu foydalanuvchiniki ekanligini tekshirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM user_shops WHERE telegram_id = ? AND shop_id = ?",
            (telegram_id, str(shop_id)),
        ) as cur:
            return await cur.fetchone() is not None


async def set_shop_verified(telegram_id: int, verified: int = 1) -> None:
    """Do'kon tasdiqlangan (bot xodim sifatida ulangan) holatini belgilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET shop_verified = ? WHERE telegram_id = ?",
            (verified, telegram_id),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  KREDITLAR (1 kredit = 1 nakladnoy)
# ═══════════════════════════════════════════════════════════════

async def get_credits(telegram_id: int) -> int:
    """Foydalanuvchining joriy kredit balansi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(credits, 0) FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0


async def consume_credit(telegram_id: int, n: int = 1) -> bool:
    """Kredit yechish (atomik). Yetarli bo'lsa True, aks holda False."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET credits = credits - ? "
            "WHERE telegram_id = ? AND COALESCE(credits, 0) >= ?",
            (n, telegram_id, n),
        )
        await db.commit()
        return cur.rowcount > 0


async def add_credits(telegram_id: int, n: int) -> None:
    """Kredit qo'shish (to'lov tasdiqlangach yoki admin qo'lda)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET credits = COALESCE(credits, 0) + ? WHERE telegram_id = ?",
            (n, telegram_id),
        )
        await db.commit()


async def refund_task_credit(task_id: int) -> int:
    """Vazifa slot OLMASDAN tugadi -> 1 kredit QAYTARISH (faqat bir marta).

    Qaytaradi: 1 = qaytarildi, 0 = qaytarilmadi.
    Qaytarilmaydi: slot olingan (booked) / allaqachon qaytarilgan / admin
    (adminda kredit yechilmagan).
    Atomik: `refunded=0` shartli UPDATE — ikki marta qaytarib yubormaydi.
    """
    from config import ADMIN_IDS
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT telegram_id, status, COALESCE(refunded, 0) AS refunded "
            "FROM slot_tasks WHERE id = ?",
            (task_id,),
        ) as c:
            r = await c.fetchone()
        if not r:
            return 0
        if r["refunded"] or r["status"] == "booked":
            return 0  # allaqachon qaytarilgan yoki slot OLINGAN — qaytarilmaydi
        if r["telegram_id"] in ADMIN_IDS:
            # Adminda kredit yechilmagan — qaytarmaymiz, faqat belgilaymiz
            await db.execute(
                "UPDATE slot_tasks SET refunded = 1 WHERE id = ?", (task_id,))
            await db.commit()
            return 0
        # Atomik: faqat refunded=0 bo'lsa belgilaymiz (bir vaqtda 2 marta bo'lmasin)
        cur = await db.execute(
            "UPDATE slot_tasks SET refunded = 1 "
            "WHERE id = ? AND COALESCE(refunded, 0) = 0",
            (task_id,),
        )
        if cur.rowcount == 0:
            await db.commit()
            return 0
        await db.execute(
            "UPDATE users SET credits = COALESCE(credits, 0) + 1 WHERE telegram_id = ?",
            (r["telegram_id"],),
        )
        await db.commit()
        logger.info("💳 Kredit qaytarildi: task=%s user=%s", task_id, r["telegram_id"])
        return 1


async def set_credits(telegram_id: int, n: int) -> None:
    """Kredit balansini aniq o'rnatish (admin)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET credits = ? WHERE telegram_id = ?",
            (n, telegram_id),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  FOYDALANUVCHILAR (USERS)
# ═══════════════════════════════════════════════════════════════

async def get_free_credits() -> int:
    """Yangi foydalanuvchiga beriladigan bepul kredit (admin sozlaydi)."""
    from config import FREE_CREDITS
    val = await get_setting("free_credits", str(FREE_CREDITS))
    try:
        return max(0, int(val))
    except (ValueError, TypeError):
        return FREE_CREDITS


async def add_user(
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None,
) -> None:
    """Yangi foydalanuvchini qo'shish yoki yangilash.

    YANGI user -> 0 kredit (bepul kredit endi registratsiyada EMAS, birinchi
    DO'KON ulanganda beriladi — cheat himoyasi, qarang: try_grant_free_credits).
    Mavjud user -> krediti O'ZGARMAYDI (faqat ism/username yangilanadi).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, full_name, username, credits)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                updated_at = datetime('now', 'localtime')
            """,
            (telegram_id, full_name, username),
        )
        await db.commit()


async def try_grant_free_credits(telegram_id: int, shop_id: str) -> int:
    """Birinchi do'kon ulanganda bepul kreditni DO'KONga bog'lab berish.

    Beriladi FAQAT agar: (a) user hali sovg'a olmagan (free_credit_taken=0) VA
    (b) bu do'kon ilgari sovg'a bermagan (free_credit_shops da yo'q).
    Berilsa — kredit qo'shiladi, user "olgan" deb belgilanadi, do'kon qayd
    etiladi. Berilgan kredit sonini qaytaradi (0 = berilmadi).

    Cheat himoyasi: yangi akkaunt ochib o'sha do'konni qayta qo'shsa ham
    (do'kon allaqachon qayd etilgan) sovg'a berilmaydi.
    """
    free = await get_free_credits()
    if free <= 0:
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COALESCE(free_credit_taken, 0) AS t FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as c:
            row = await c.fetchone()
        if row and row["t"]:
            return 0  # user allaqachon sovg'a olgan
        async with db.execute(
            "SELECT 1 FROM free_credit_shops WHERE shop_id = ?",
            (str(shop_id),),
        ) as c:
            used = await c.fetchone()
        if used:
            return 0  # do'kon allaqachon sovg'a bergan (cheat bloklandi)
        await db.execute(
            "UPDATE users SET credits = COALESCE(credits, 0) + ?, "
            "free_credit_taken = 1 WHERE telegram_id = ?",
            (free, telegram_id),
        )
        await db.execute(
            "INSERT OR IGNORE INTO free_credit_shops (shop_id, telegram_id) "
            "VALUES (?, ?)",
            (str(shop_id), telegram_id),
        )
        await db.commit()
        return free


async def get_user(telegram_id: int) -> Optional[dict]:
    """Foydalanuvchini Telegram ID bo'yicha olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_token(telegram_id: int, token: str) -> None:
    """Foydalanuvchining API tokenini saqlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users SET api_token = ?, updated_at = datetime('now', 'localtime')
            WHERE telegram_id = ?
            """,
            (token, telegram_id),
        )
        await db.commit()


async def get_users_count() -> int:
    """Jami foydalanuvchilar sonini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


#  Broadcast auditoriyasi (nishonli xabar yuborish)
BROADCAST_TARGETS = {
    "all":      "Hammaga",
    "no_shop":  "Do'kon ulamaganlar",
    "has_shop": "Do'koni borlar (mijozlar)",
}


async def get_broadcast_users(target: str = "all") -> List[int]:
    """Nishon bo'yicha telegram_id ro'yxati.

    • all      — barcha foydalanuvchilar
    • no_shop  — /start bosgan, lekin do'kon ULAMAGAN ("o'lik" klientlar)
    • has_shop — do'koni bor (faol mijozlar)

    Noma'lum nishon -> 'all' (xavfsiz zaxira).
    """
    where = {
        "no_shop": "WHERE NOT EXISTS (SELECT 1 FROM user_shops s "
                   "WHERE s.telegram_id = u.telegram_id)",
        "has_shop": "WHERE EXISTS (SELECT 1 FROM user_shops s "
                    "WHERE s.telegram_id = u.telegram_id)",
    }.get(target, "")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT u.telegram_id FROM users u {where} ORDER BY u.created_at DESC"
        ) as c:
            return [r[0] for r in await c.fetchall()]


async def get_broadcast_counts() -> dict:
    """Har bir nishon uchun foydalanuvchi soni (admin ko'rinishi uchun)."""
    return {t: len(await get_broadcast_users(t)) for t in BROADCAST_TARGETS}


async def get_all_users() -> List[dict]:
    """Barcha foydalanuvchilarni olish (admin uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
#  SLOT VAZIFALARI (TASKS)
# ═══════════════════════════════════════════════════════════════

async def create_task(
    telegram_id: int,
    shop_id: str,
    nakladnoy_number: str,
    warehouse: Optional[str] = None,
    preferred_date: Optional[str] = None,
    time_preference: str = "any",
    target_date: Optional[str] = None,
    invoice_display: Optional[str] = None,
) -> int:
    """Yangi slot qidirish vazifasini yaratish. Task ID qaytaradi.

    target_date — aniq kun (ISO: "2026-07-01"). Berilsa faqat shu kunda
    slot qidiriladi. None = istalgan sana (deadline gacha).
    invoice_display — user ko'radigan invoiceNumber (13 xonali); None bo'lsa
    ko'rsatishda nakladnoy_number (ichki id) ishlatiladi.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO slot_tasks
                (telegram_id, shop_id, nakladnoy_number, warehouse,
                 preferred_date, time_preference, target_date, invoice_display)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, shop_id, nakladnoy_number, warehouse,
             preferred_date, time_preference, target_date, invoice_display),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_tasks(telegram_id: Optional[int] = None) -> List[dict]:
    """Faol vazifalarni olish. telegram_id berilmasa — hamma faol vazifalar."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if telegram_id:
            query = """
                SELECT st.*, u.api_token
                FROM slot_tasks st
                JOIN users u ON st.telegram_id = u.telegram_id
                WHERE st.telegram_id = ? AND st.status IN ('waiting', 'checking')
                ORDER BY st.created_at DESC
            """
            async with db.execute(query, (telegram_id,)) as cursor:
                rows = await cursor.fetchall()
        else:
            query = """
                SELECT st.*, u.api_token
                FROM slot_tasks st
                JOIN users u ON st.telegram_id = u.telegram_id
                WHERE st.status IN ('waiting', 'checking')
                ORDER BY st.created_at ASC
            """
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_task_by_id(task_id: int) -> Optional[dict]:
    """Vazifani ID bo'yicha olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT st.*, u.api_token
            FROM slot_tasks st
            JOIN users u ON st.telegram_id = u.telegram_id
            WHERE st.id = ?
            """,
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_tasks_history(
    telegram_id: int,
    limit: int = 20,
) -> List[dict]:
    """Foydalanuvchining barcha vazifalari (tarix bilan)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM slot_tasks
            WHERE telegram_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_task_status(
    task_id: int,
    status: str,
    slot_info: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Vazifa statusini yangilash.

    reason — "error" holatida sabab (admin panelда ko'rsatiladi).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "booked":
            await db.execute(
                """
                UPDATE slot_tasks SET
                    status = ?, slot_info = ?,
                    booked_at = datetime('now', 'localtime')
                WHERE id = ?
                """,
                (status, slot_info, task_id),
            )
        else:
            await db.execute(
                "UPDATE slot_tasks SET status = ?, error_reason = ? WHERE id = ?",
                (status, reason, task_id),
            )
        await db.commit()

    # ── KREDIT QAYTARISH (connection yopilgandan keyin — nested yo'q) ──
    # Vazifa slot OLMASDAN tugadi (error/cancelled) -> 1 kredit qaytariladi.
    # refund_task_credit o'zi tekshiradi: booked/allaqachon-qaytarilgan/admin.
    if status in ("error", "cancelled"):
        try:
            await refund_task_credit(task_id)
        except Exception as e:
            logger.error("Kredit qaytarishda xato (task=%s): %s", task_id, e)


async def increment_attempts(task_id: int) -> None:
    """Vazifaning urinishlar sonini oshirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE slot_tasks SET
                attempts = attempts + 1,
                last_check = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (task_id,),
        )
        await db.commit()


async def add_attempts_batch(deltas: dict) -> None:
    """Bir nechta vazifaning urinishlar sonini BITTA tranzaksiyada oshirish.

    deltas: {task_id: qo'shiladigan_son}. MIQYOS — har vazifani alohida yozish
    o'rniga yig'ilgan hisoblarni bir marta yozadi (DB yozuv yukini kamaytiradi).
    """
    if not deltas:
        return
    rows = [(int(n), int(tid)) for tid, n in deltas.items() if n]
    if not rows:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            UPDATE slot_tasks SET
                attempts = attempts + ?,
                last_check = datetime('now', 'localtime')
            WHERE id = ?
            """,
            rows,
        )
        await db.commit()


async def widen_task_to_slot(task_id: int, telegram_id: int,
                             slot_ms: int, slot_date: str) -> bool:
    """"Sana taklifi" qabul qilinganda — vazifani o'sha eng erta bo'sh slotni
    band qilishga moslaydi.

    preferred_date (muddat oxiri) = slot_ms + 1 daqiqa bufer (tf <= deadline
    o'tsin), target_date = slot kuni (aynan shu kun), time_preference = 'any'
    (ertalab/kechqurun filtri to'smasin). Faqat egasining faol vazifasiga.
    """
    buffered = int(slot_ms) + 60_000
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE slot_tasks
            SET preferred_date = ?, target_date = ?, time_preference = 'any'
            WHERE id = ? AND telegram_id = ? AND status IN ('waiting', 'checking')
            """,
            (str(buffered), slot_date, task_id, telegram_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def cancel_task(task_id: int, telegram_id: int) -> bool:
    """Vazifani bekor qilish. Muvaffaqiyatli bo'lsa True qaytaradi.

    Slot olinmagani uchun 1 kredit QAYTARILADI.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE slot_tasks SET status = 'cancelled'
            WHERE id = ? AND telegram_id = ? AND status IN ('waiting', 'checking')
            """,
            (task_id, telegram_id),
        )
        await db.commit()
        ok = cursor.rowcount > 0
    if ok:
        try:
            await refund_task_credit(task_id)
        except Exception as e:
            logger.error("Kredit qaytarishda xato (task=%s): %s", task_id, e)
    return ok


# ═══════════════════════════════════════════════════════════════
#  STATISTIKA
# ═══════════════════════════════════════════════════════════════

async def get_booked_count() -> int:
    """Jami olingan slotlar sonini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE status = 'booked'"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_active_tasks_count() -> int:
    """Faol vazifalar sonini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE status IN ('waiting', 'checking')"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_user_stats(telegram_id: int) -> dict:
    """Foydalanuvchining shaxsiy statistikasi."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Faol vazifalar
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE telegram_id = ? AND status IN ('waiting', 'checking')",
            (telegram_id,),
        ) as cursor:
            active = (await cursor.fetchone())[0]

        # Olingan slotlar
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE telegram_id = ? AND status = 'booked'",
            (telegram_id,),
        ) as cursor:
            booked = (await cursor.fetchone())[0]

        # Jami urinishlar
        async with db.execute(
            "SELECT COALESCE(SUM(attempts), 0) FROM slot_tasks WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            total_attempts = (await cursor.fetchone())[0]

        # Bekor qilinganlar
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE telegram_id = ? AND status = 'cancelled'",
            (telegram_id,),
        ) as cursor:
            cancelled = (await cursor.fetchone())[0]

        return {
            "active": active,
            "booked": booked,
            "total_attempts": total_attempts,
            "cancelled": cancelled,
        }


async def get_total_stats() -> dict:
    """Umumiy bot statistikasi (admin uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            users = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE status IN ('waiting', 'checking')"
        ) as c:
            active = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM slot_tasks WHERE status = 'booked'"
        ) as c:
            booked = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM slot_tasks") as c:
            total_tasks = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COALESCE(SUM(attempts), 0) FROM slot_tasks"
        ) as c:
            total_attempts = (await c.fetchone())[0]

        return {
            "users": users,
            "active_tasks": active,
            "booked_slots": booked,
            "total_tasks": total_tasks,
            "total_attempts": total_attempts,
        }


# ═══════════════════════════════════════════════════════════════
#  ADMIN FUNKSIYALARI
# ═══════════════════════════════════════════════════════════════

async def toggle_user_active(telegram_id: int) -> bool:
    """Foydalanuvchining is_active holatini almashtirish (0↔1).
    Yangi holatni qaytaradi: True = faol, False = bloklangan."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Hozirgi holatni olish
        async with db.execute(
            "SELECT is_active FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return False
            current = row[0]

        new_status = 0 if current else 1
        await db.execute(
            """
            UPDATE users SET is_active = ?, updated_at = datetime('now', 'localtime')
            WHERE telegram_id = ?
            """,
            (new_status, telegram_id),
        )
        await db.commit()
        return bool(new_status)


async def get_credits_report() -> dict:
    """Kredit taqsimoti + daromad xulosasi (admin 'Kredit hisoboti' uchun).

    Daromad = tasdiqlangan VA test emas VA chiqarilmagan user (test/sherik kirmaydi).
    """
    excluded = await get_revenue_excluded_ids()
    _ids = ",".join(str(int(x)) for x in excluded)

    def _mk_rev(pfx: str = "") -> str:
        s = "{p}status='confirmed' AND COALESCE({p}is_test,0)=0".format(p=pfx)
        if excluded:
            s += " AND {p}telegram_id NOT IN ({ids})".format(p=pfx, ids=_ids)
        return s

    rev = _mk_rev("")        # bitta-jadval (payments) so'rovlari uchun
    rev_p = _mk_rev("p.")    # JOIN so'rovi uchun (telegram_id noaniqligini oldini oladi)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async def scalar(q: str, *a):
            async with db.execute(q, a) as c:
                r = await c.fetchone()
                return r[0] if r and r[0] is not None else 0

        rep = {
            "total_users":   await scalar("SELECT COUNT(*) FROM users"),
            "with_credits":  await scalar("SELECT COUNT(*) FROM users WHERE COALESCE(credits,0)>0"),
            "total_credits": await scalar("SELECT COALESCE(SUM(credits),0) FROM users"),
            "d0":    await scalar("SELECT COUNT(*) FROM users WHERE COALESCE(credits,0)=0"),
            "d1_5":  await scalar("SELECT COUNT(*) FROM users WHERE COALESCE(credits,0) BETWEEN 1 AND 5"),
            "d6_10": await scalar("SELECT COUNT(*) FROM users WHERE COALESCE(credits,0) BETWEEN 6 AND 10"),
            "d11":   await scalar("SELECT COUNT(*) FROM users WHERE COALESCE(credits,0) >= 11"),
            # DAROMAD (test/sherik chiqarilgan):
            "paid_count":     await scalar("SELECT COUNT(*) FROM payments WHERE " + rev),
            "paid_amount":    await scalar("SELECT COALESCE(SUM(amount),0) FROM payments WHERE " + rev),
            "paid_credits":   await scalar("SELECT COALESCE(SUM(credits),0) FROM payments WHERE " + rev),
            "payers":         await scalar("SELECT COUNT(DISTINCT telegram_id) FROM payments WHERE " + rev),
            "pending_count":  await scalar("SELECT COUNT(*) FROM payments WHERE status='pending'"),
            "pending_amount": await scalar("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='pending'"),
            # Test/sherik to'lovlar (alohida, ma'lumot uchun):
            "test_amount":    await scalar("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='confirmed' AND (COALESCE(is_test,0)=1{})".format(
                "" if not excluded else " OR telegram_id IN ({})".format(",".join(str(int(x)) for x in excluded)))),
        }
        async with db.execute(
            "SELECT telegram_id, username, full_name, credits FROM users "
            "WHERE COALESCE(credits,0) > 5 ORDER BY credits DESC LIMIT 10"
        ) as c:
            rep["top_holders"] = [dict(r) for r in await c.fetchall()]
        async with db.execute(
            "SELECT p.telegram_id, u.username, COUNT(*) AS cnt, "
            "COALESCE(SUM(p.amount),0) AS amt "
            "FROM payments p LEFT JOIN users u ON p.telegram_id=u.telegram_id "
            "WHERE " + rev_p + " GROUP BY p.telegram_id "
            "ORDER BY amt DESC LIMIT 8"
        ) as c:
            rep["top_payers"] = [dict(r) for r in await c.fetchall()]
        return rep


async def get_recent_error_tasks(limit: int = 30) -> List[dict]:
    """Oxirgi 'error' statusli vazifalar (sabab bilan) — admin panel uchun."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM slot_tasks WHERE status = 'error' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_tasks_summary() -> dict:
    """Vazifalarni status bo'yicha guruhlash va sonini qaytarish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT status, COUNT(*) FROM slot_tasks GROUP BY status"
        ) as cursor:
            rows = await cursor.fetchall()

        summary = {
            "waiting": 0,
            "checking": 0,
            "booked": 0,
            "cancelled": 0,
            "error": 0,
        }
        for row in rows:
            if row[0] in summary:
                summary[row[0]] = row[1]
            else:
                summary[row[0]] = row[1]
        return summary


# ═══════════════════════════════════════════════════════════════
#  LOGLAR
# ═══════════════════════════════════════════════════════════════

async def add_log(task_id: int, status: str, response: str = "") -> None:
    """Tekshirish logini qo'shish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO check_logs (task_id, status, response) VALUES (?, ?, ?)",
            (task_id, status, response),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  TO'LOVLAR (PAYMENTS)
# ═══════════════════════════════════════════════════════════════

async def create_payment(
    telegram_id: int,
    amount: int,
    order_id: str,
    credits: int = 0,
) -> None:
    """Yangi to'lov yozuvini yaratish (credits = sotib olinayotgan kredit soni)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO payments (telegram_id, order_id, amount, credits)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, order_id, amount, credits),
        )
        await db.commit()


async def confirm_payment(order_id: str) -> bool:
    """To'lovni tasdiqlash va KREDIT qo'shish. Muvaffaqiyatli bo'lsa True."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE order_id = ?",
            (order_id,),
        ) as cursor:
            payment = await cursor.fetchone()
            if not payment:
                return False
            payment = dict(payment)

        if payment["status"] == "confirmed":
            return True  # Allaqachon tasdiqlangan

        await db.execute(
            """
            UPDATE payments SET
                status = 'confirmed',
                confirmed_at = datetime('now', 'localtime')
            WHERE order_id = ?
            """,
            (order_id,),
        )

        # KREDIT qo'shish (1 kredit = 1 nakladnoy)
        credits = int(payment.get("credits") or 0)
        if credits > 0:
            await db.execute(
                "UPDATE users SET credits = COALESCE(credits, 0) + ?, "
                "updated_at = datetime('now', 'localtime') WHERE telegram_id = ?",
                (credits, payment["telegram_id"]),
            )

        await db.commit()
        logger.info(
            "To'lov tasdiqlandi: order=%s, user=%s, amount=%s, credits=+%s",
            order_id, payment["telegram_id"], payment["amount"], credits,
        )
        return True


async def reject_payment(order_id: str) -> bool:
    """Kutilayotgan (pending) to'lovni rad etish. Muvaffaqiyatli bo'lsa True.

    Faqat 'pending' holatdagi to'lov rad etiladi (tasdiqlangan/rad etilganга tegmaydi).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE payments SET status = 'cancelled' "
            "WHERE order_id = ? AND status = 'pending'",
            (order_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_payment(order_id: str) -> Optional[dict]:
    """To'lov ma'lumotlarini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE order_id = ?",
            (order_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_recent_payments(limit: int = 20) -> List[dict]:
    """Oxirgi to'lovlar ro'yxatini olish (admin uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT p.*, u.full_name, u.username
            FROM payments p
            LEFT JOIN users u ON p.telegram_id = u.telegram_id
            ORDER BY p.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_payment_summary(telegram_id: int) -> dict:
    """Foydalanuvchi to'lovlari xulosasi (admin user-detail uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT
              SUM(CASE WHEN status='confirmed' THEN 1 ELSE 0 END)        AS paid_count,
              COALESCE(SUM(CASE WHEN status='confirmed' THEN amount  ELSE 0 END),0) AS paid_amount,
              COALESCE(SUM(CASE WHEN status='confirmed' THEN credits ELSE 0 END),0) AS paid_credits,
              SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END)          AS pending_count
            FROM payments WHERE telegram_id = ?
            """,
            (telegram_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}


async def update_subscription(
    telegram_id: int,
    tier: str,
    expires_at: Optional[str] = None,
) -> None:
    """Foydalanuvchi obunasini yangilash ('premium' yoki 'free')."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users SET
                subscription = ?,
                subscription_expires_at = ?,
                updated_at = datetime('now', 'localtime')
            WHERE telegram_id = ?
            """,
            (tier, expires_at, telegram_id),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  DO'KON MA'LUMOTLARI
# ═══════════════════════════════════════════════════════════════

async def save_shop_info(
    telegram_id: int,
    shop_id: str,
    shop_name: Optional[str] = None,
) -> None:
    """Foydalanuvchining do'kon ma'lumotlarini saqlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users SET
                shop_id = ?,
                shop_name = ?,
                updated_at = datetime('now', 'localtime')
            WHERE telegram_id = ?
            """,
            (shop_id, shop_name, telegram_id),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  SOZLAMALAR (SETTINGS)
# ═══════════════════════════════════════════════════════════════

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Sozlama qiymatini olish. Topilmasa default qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    """Sozlama qiymatini saqlash yoki yangilash (upsert)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, datetime('now', 'localtime'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  TO'LOVLAR — DAROMAD
# ═══════════════════════════════════════════════════════════════
# Eslatma: create_payment / confirm_payment / get_payment /
# get_recent_payments yuqorida (TO'LOVLAR (PAYMENTS) bo'limida) bir
# marta to'liq aniqlangan. Bu yerda ilgari ularning TAKRORIY nusxalari
# bor edi — ayniqsa confirm_payment premium BERMAYDIGAN va None
# qaytaradigan buzuq versiya bilan. Ular olib tashlandi.


async def get_revenue_stats() -> dict:
    """Daromad statistikasini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Jami
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'confirmed'"
        ) as cur:
            total = (await cur.fetchone())[0]
        # Bugungi
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'confirmed' AND date(confirmed_at) = date('now', 'localtime')"
        ) as cur:
            today = (await cur.fetchone())[0]
        # Oylik
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'confirmed' AND confirmed_at >= datetime('now', 'localtime', 'start of month')"
        ) as cur:
            monthly = (await cur.fetchone())[0]
        # Pending count
        async with db.execute(
            "SELECT COUNT(*) FROM payments WHERE status = 'pending'"
        ) as cur:
            pending = (await cur.fetchone())[0]

        return {
            "total": total, "today": today,
            "monthly": monthly, "pending_count": pending,
        }


# ═══════════════════════════════════════════════════════════════
#  PROMO KODLAR
# ═══════════════════════════════════════════════════════════════

async def create_promo(
    code: str,
    days: int = 30,
    max_uses: int = 1,
) -> bool:
    """Yangi promo kod yaratish. Muvaffaqiyatli bo'lsa True qaytaradi."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO promo_codes (code, days, max_uses)
                VALUES (?, ?, ?)
                """,
                (code.upper(), days, max_uses),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def use_promo(code: str, telegram_id: int) -> dict:
    """Promo kodni ishlatish. Premium beradi.

    Returns:
        dict: {"success": bool, "days": int, "error": Optional[str]}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promo_codes WHERE code = ?",
            (code.upper(),),
        ) as cursor:
            promo = await cursor.fetchone()

        if not promo:
            return {"success": False, "days": 0, "error": "Promo kod topilmadi."}

        promo = dict(promo)

        if not promo["is_active"]:
            return {"success": False, "days": 0, "error": "Promo kod faol emas."}

        if promo["used_count"] >= promo["max_uses"]:
            return {"success": False, "days": 0, "error": "Promo kod limiti tugagan."}

        # Promo kodni ishlatish
        await db.execute(
            "UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?",
            (code.upper(),),
        )

        # Foydalanuvchini premium qilish
        from datetime import timedelta
        expires = datetime.now() + timedelta(days=promo["days"])
        expires_str = expires.strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            """
            UPDATE users SET
                subscription = 'premium',
                subscription_expires_at = ?,
                updated_at = datetime('now', 'localtime')
            WHERE telegram_id = ?
            """,
            (expires_str, telegram_id),
        )

        await db.commit()

        logger.info(
            "Promo kod ishlatildi: code=%s, user=%s, days=%s",
            code, telegram_id, promo["days"],
        )
        return {"success": True, "days": promo["days"], "error": None}


async def get_promos() -> List[dict]:
    """Barcha promo kodlarni olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promo_codes ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def deactivate_promo(code: str) -> bool:
    """Promo kodni o'chirish. Muvaffaqiyatli bo'lsa True qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE promo_codes SET is_active = 0 WHERE code = ?",
            (code.upper(),),
        )
        await db.commit()
        return cursor.rowcount > 0


# ═══════════════════════════════════════════════════════════════
#  DAROMAD HISOBLASH
# ═══════════════════════════════════════════════════════════════

async def get_revenue_excluded_ids() -> list:
    """Daromaddan DOIM chiqariladigan telegram_id lar (o'zi + sheriklar)."""
    val = await get_setting("revenue_excluded_ids", "")
    ids = []
    for x in (val or "").replace(" ", "").split(","):
        s = x.strip()
        if s.lstrip("-").isdigit():
            ids.append(int(s))
    return ids


async def get_total_revenue() -> dict:
    """Umumiy daromad hisoboti.

    DAROMAD = tasdiqlangan to'lov VA test emas (is_test=0) VA daromaddan
    chiqarilmagan user. Test/sherik to'lovlari HISOBGA KIRMAYDI.
    """
    excluded = await get_revenue_excluded_ids()
    excl = ""
    if excluded:
        excl = " AND telegram_id NOT IN ({})".format(
            ",".join(str(int(x)) for x in excluded))
    rev = "status = 'confirmed' AND COALESCE(is_test,0)=0" + excl
    async with aiosqlite.connect(DB_PATH) as db:
        async def revsum(extra: str = "") -> int:
            async with db.execute(
                "SELECT COALESCE(SUM(amount),0) FROM payments WHERE " + rev + extra
            ) as c:
                return (await c.fetchone())[0]
        total = await revsum()
        today = await revsum(" AND date(confirmed_at)=date('now','localtime')")
        weekly = await revsum(" AND confirmed_at >= datetime('now','-7 days','localtime')")
        monthly = await revsum(" AND confirmed_at >= datetime('now','-30 days','localtime')")
        async with db.execute("SELECT COUNT(*) FROM payments WHERE " + rev) as c:
            count = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM payments WHERE status = 'pending'"
        ) as c:
            pending = (await c.fetchone())[0]
        return {
            "total": total,
            "today": today,
            "weekly": weekly,
            "monthly": monthly,
            "count": count,
            "pending": pending,
        }
