"""
INNASLOT Admin Mini App — Backend API (FastAPI).

Mavjud `database.py` funksiyalarini QAYTA ishlatadi (bot bilan bir xil DB).
Auth: Telegram Mini App `initData` HMAC tekshiruvi -> FAQAT admin.
Botning ishlayotgan jarayoniga TEGMAYDI (alohida jarayon/venv).
"""
import hashlib
import hmac
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qsl

import aiosqlite
from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import database as db
from config import BOT_TOKEN, ADMIN_ID, ADMIN_IDS, UZUM_SESSION_FILE

app = FastAPI(title="INNASLOT Admin API", version="2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_ADMINS = set(ADMIN_IDS) | {ADMIN_ID}
UZB = timezone(timedelta(hours=5))
PAGE = 12


# ── Auth ──
def _verify_init_data(init_data: str) -> int:
    if not init_data:
        raise HTTPException(401, "init data yo'q")
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = parsed.pop("hash", None)
        if not recv_hash:
            raise ValueError()
        dcs = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            raise ValueError()
        return int(json.loads(parsed.get("user", "{}")).get("id", 0))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "init data noto'g'ri")


async def admin_only(x_telegram_init_data: str = Header(default="")) -> int:
    uid = _verify_init_data(x_telegram_init_data)
    if uid not in _ADMINS:
        raise HTTPException(403, "ruxsat yo'q")
    return uid


# ── Yordamchilar ──
def _session_ok() -> bool:
    try:
        with open(UZUM_SESSION_FILE) as f:
            return float(json.load(f).get("expires_at", 0)) > time.time()
    except Exception:
        return False


def _tg_send(chat_id: int, text: str) -> bool:
    try:
        body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=10))
        return bool(r.get("ok"))
    except Exception:
        return False


def _slot_when(slot_json) -> str:
    """slot_info (JSON) dan 'sana vaqt' matni."""
    try:
        s = json.loads(slot_json) if isinstance(slot_json, str) else (slot_json or {})
        tf = s.get("timeFrom")
        tt = s.get("timeTo")
        if not tf:
            return "—"
        a = datetime.fromtimestamp(tf / 1000, tz=UZB)
        out = a.strftime("%d.%m.%Y %H:%M")
        if tt:
            out += "-" + datetime.fromtimestamp(tt / 1000, tz=UZB).strftime("%H:%M")
        return out
    except Exception:
        return "—"


def _err_reason(t: dict) -> str:
    r = t.get("error_reason")
    if r:
        return r
    att = t.get("attempts", 0) or 0
    if att >= 50000:
        return "Limit: 50000 urinish"
    pd = t.get("preferred_date")
    try:
        if pd and int(pd) < int(time.time() * 1000):
            return "Muddat o'tdi"
    except (ValueError, TypeError):
        pass
    return "Boshqa (band/xato)"


# ════════════════════════ ENDPOINTLAR ════════════════════════
@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/dashboard")
async def dashboard(uid: int = Depends(admin_only)):
    rep = await db.get_credits_report()
    rev = await db.get_total_revenue()
    return {
        "users": await db.get_users_count(),
        "active_tasks": await db.get_active_tasks_count(),
        "booked": await db.get_booked_count(),
        "total_credits": rep["total_credits"],
        "revenue": rev["total"],
        "test_amount": rep["test_amount"],
        "pending_count": rev["pending"],
        "errors": len(await db.get_recent_error_tasks(1000)),
        "session_ok": _session_ok(),
        "chart": await _revenue_chart_7d(),
    }


async def _revenue_chart_7d() -> list:
    excluded = await db.get_revenue_excluded_ids()
    excl = " AND telegram_id NOT IN ({})".format(
        ",".join(str(int(x)) for x in excluded)) if excluded else ""
    out = []
    async with aiosqlite.connect(db.DB_PATH) as con:
        for i in range(6, -1, -1):
            async with con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='confirmed' "
                "AND COALESCE(is_test,0)=0" + excl +
                " AND date(confirmed_at)=date('now', ?, 'localtime')", (f"-{i} days",)) as c:
                out.append((await c.fetchone())[0])
    mx = max(out) or 1
    return [round(v / mx * 100) for v in out]


# ── Foydalanuvchilar ──
@app.get("/api/users")
async def users(page: int = 0, q: str = "", uid: int = Depends(admin_only)):
    q = (q or "").strip().lower()
    async with aiosqlite.connect(db.DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        where, args = "", []
        if q:
            where = ("WHERE lower(COALESCE(full_name,'')) LIKE ? OR "
                     "lower(COALESCE(username,'')) LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?")
            args = [f"%{q}%", f"%{q}%", f"%{q}%"]
        total = (await (await con.execute(
            f"SELECT COUNT(*) FROM users {where}", args)).fetchone())[0]
        rows = await (await con.execute(
            f"SELECT telegram_id, full_name, username, COALESCE(credits,0) credits, "
            f"COALESCE(is_active,1) is_active, api_token, created_at FROM users {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?", args + [PAGE, page * PAGE])).fetchall()
    return {
        "total": total, "page": page, "pages": max(1, (total + PAGE - 1) // PAGE),
        "users": [{
            "id": r["telegram_id"], "name": r["full_name"] or "Nomsiz",
            "username": r["username"], "credits": r["credits"],
            "active": bool(r["is_active"]), "connected": bool(r["api_token"]),
            "created": (r["created_at"] or "")[:10],
        } for r in rows],
    }


@app.get("/api/user/{tid}")
async def user_detail(tid: int, uid: int = Depends(admin_only)):
    u = await db.get_user(tid)
    if not u:
        raise HTTPException(404, "topilmadi")
    shops = await db.get_user_shops(tid)
    pay = await db.get_user_payment_summary(tid)
    stats = await db.get_user_stats(tid)
    return {
        "id": tid, "name": u.get("full_name") or "Nomsiz", "username": u.get("username"),
        "active": bool(u.get("is_active", 1)), "credits": u.get("credits", 0) or 0,
        "free_taken": bool(u.get("free_credit_taken")),
        "created": u.get("created_at", "—"),
        "shops": [{"shop_id": s["shop_id"], "name": s.get("shop_name")} for s in shops],
        "pay": {"count": pay.get("paid_count", 0) or 0, "amount": pay.get("paid_amount", 0) or 0,
                "credits": pay.get("paid_credits", 0) or 0, "pending": pay.get("pending_count", 0) or 0},
        "stats": {"active": stats.get("active", 0), "booked": stats.get("booked", 0),
                  "attempts": stats.get("total_attempts", 0), "cancelled": stats.get("cancelled", 0)},
    }


@app.post("/api/user/{tid}/ban")
async def user_ban(tid: int, uid: int = Depends(admin_only)):
    new = await db.toggle_user_active(tid)
    return {"ok": True, "active": bool(new)}


@app.post("/api/user/{tid}/message")
async def user_message(tid: int, body: dict = Body(...), uid: int = Depends(admin_only)):
    """Admin -> foydalanuvchiga BOT orqali to'g'ridan-to'g'ri xabar.

    Username YO'Q userlarga ham yozish mumkin (telegram_id orqali sendMessage).
    """
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "matn bo'sh")
    ok = _tg_send(tid, text)
    return {"ok": ok}


@app.post("/api/user/{tid}/credits")
async def user_add_credits(tid: int, body: dict = Body(...), uid: int = Depends(admin_only)):
    n = int(body.get("amount", 0))
    if n == 0:
        raise HTTPException(400, "amount 0")
    if n > 0:
        await db.add_credits(tid, n)
    else:
        cur = await db.get_credits(tid)
        await db.set_credits(tid, max(0, cur + n))
    bal = await db.get_credits(tid)
    if n > 0:
        _tg_send(tid, f"🎁 Sizga admin tomonidan <b>{n} kredit</b> qo'shildi.\n💰 Balans: <b>{bal}</b>")
    return {"ok": True, "credits": bal}


# ── To'lovlar ──
@app.get("/api/payments")
async def payments(status: str = "", uid: int = Depends(admin_only)):
    async with aiosqlite.connect(db.DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        where, args = "", []
        if status in ("pending", "confirmed", "cancelled"):
            where = "WHERE p.status = ?"
            args = [status]
        rows = await (await con.execute(
            f"SELECT p.order_id, p.telegram_id, p.amount, COALESCE(p.credits,0) credits, "
            f"p.status, p.created_at, COALESCE(p.is_test,0) is_test, u.full_name, u.username "
            f"FROM payments p LEFT JOIN users u ON p.telegram_id=u.telegram_id "
            f"{where} ORDER BY p.created_at DESC LIMIT 50", args)).fetchall()
    return [{
        "order_id": r["order_id"], "uid": r["telegram_id"],
        "name": r["full_name"] or "Nomsiz", "username": r["username"],
        "amount": r["amount"], "credits": r["credits"], "status": r["status"],
        "created": (r["created_at"] or "")[:16], "is_test": bool(r["is_test"]),
    } for r in rows]


@app.post("/api/payment/{order_id}/confirm")
async def payment_confirm(order_id: str, uid: int = Depends(admin_only)):
    ok = await db.confirm_payment(order_id)
    if ok:
        p = await db.get_payment(order_id)
        if p:
            bal = await db.get_credits(p["telegram_id"])
            _tg_send(p["telegram_id"],
                     f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n🧾 +{p.get('credits',0)} kredit qo'shildi.\n💰 Balans: <b>{bal}</b>")
    return {"ok": ok}


@app.post("/api/payment/{order_id}/reject")
async def payment_reject(order_id: str, uid: int = Depends(admin_only)):
    ok = await db.reject_payment(order_id)
    if ok:
        p = await db.get_payment(order_id)
        if p:
            _tg_send(p["telegram_id"], f"❌ <b>To'lovingiz rad etildi.</b>\n📋 {order_id}")
    return {"ok": ok}


# ── Hisobot ──
@app.get("/api/report")
async def report(uid: int = Depends(admin_only)):
    r = await db.get_credits_report()
    return r


# ── Vazifalar / Xatoliklar ──
@app.get("/api/tasks")
async def tasks(status: str = "active", uid: int = Depends(admin_only)):
    if status == "error":
        rows = await db.get_recent_error_tasks(40)
        return [{
            "id": t["id"], "uid": t["telegram_id"], "shop_id": t.get("shop_id"),
            "reason": _err_reason(t), "attempts": t.get("attempts", 0),
            "created": (t.get("created_at") or "")[:16],
        } for t in rows]
    rows = await db.get_active_tasks()
    return [{
        "id": t["id"], "uid": t["telegram_id"], "shop_id": t.get("shop_id"),
        "nakladnoy": t.get("invoice_display") or t.get("nakladnoy_number"),
        "attempts": t.get("attempts", 0), "target": t.get("target_date"),
        "pref": t.get("time_preference") or "any",
        "created": (t.get("created_at") or "")[:16],
    } for t in rows]


# ── Band qilinganlar (kim, qachonga) ──
@app.get("/api/booked")
async def booked(uid: int = Depends(admin_only)):
    async with aiosqlite.connect(db.DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        rows = await (await con.execute(
            "SELECT t.id, t.telegram_id, t.shop_id, t.nakladnoy_number, t.invoice_display, "
            "t.slot_info, t.booked_at, u.full_name, u.username "
            "FROM slot_tasks t LEFT JOIN users u ON t.telegram_id=u.telegram_id "
            "WHERE t.status='booked' ORDER BY t.booked_at DESC LIMIT 50")).fetchall()
    return [{
        "id": r["id"], "uid": r["telegram_id"],
        "name": r["full_name"] or "Nomsiz", "username": r["username"],
        "shop_id": r["shop_id"],
        "nakladnoy": r["invoice_display"] or r["nakladnoy_number"],
        "when": _slot_when(r["slot_info"]),
        "booked_at": (r["booked_at"] or "")[:16],
    } for r in rows]


# ── Sozlamalar ──
@app.get("/api/settings")
async def settings_get(uid: int = Depends(admin_only)):
    return {
        "credit_price": int(await db.get_setting("credit_price", "20000") or 20000),
        "free_credits": int(await db.get_setting("free_credits", "5") or 5),
        "card_number": await db.get_setting("payment_card_number", "") or "",
        "card_holder": await db.get_setting("payment_card_holder", "") or "",
        "excluded_ids": await db.get_setting("revenue_excluded_ids", "") or "",
        "session_ok": _session_ok(),
    }


@app.post("/api/settings")
async def settings_set(body: dict = Body(...), uid: int = Depends(admin_only)):
    keys = {
        "credit_price": "credit_price", "free_credits": "free_credits",
        "card_number": "payment_card_number", "card_holder": "payment_card_holder",
        "excluded_ids": "revenue_excluded_ids",
    }
    for k, sk in keys.items():
        if k in body and body[k] is not None:
            await db.set_setting(sk, str(body[k]))
    return await settings_get(uid)


# ── Broadcast ──
@app.post("/api/broadcast")
async def broadcast(body: dict = Body(...), uid: int = Depends(admin_only)):
    text = (body.get("text") or "").strip()
    target = body.get("target", "all")
    if not text:
        raise HTTPException(400, "matn bo'sh")
    async with aiosqlite.connect(db.DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        where = "WHERE COALESCE(is_active,1)=1"
        if target == "credits":
            where += " AND COALESCE(credits,0) > 0"
        elif target == "connected":
            where += " AND api_token IS NOT NULL"
        rows = await (await con.execute(
            f"SELECT telegram_id FROM users {where}")).fetchall()
    sent = 0
    for r in rows:
        if _tg_send(r["telegram_id"], text):
            sent += 1
        time.sleep(0.05)  # Telegram rate-limit
    return {"ok": True, "sent": sent, "total": len(rows)}
