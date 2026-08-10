"""Telegram Mini App autentifikatsiyasi (initData HMAC).

Mavjud admin panelidagi tekshiruv bilan bir xil, LEKIN qo'shimcha
`auth_date` muddati bilan: usiz bir marta o'g'irlangan initData abadiy
ishlayveradi. Bu yerda pul (ballar) bor — muddat SHART.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from config import BOT_TOKEN
from superapp.config import INITDATA_TTL


class AuthError(Exception):
    pass


def verify_init_data(init_data: str, ttl: int = 0) -> dict:
    """initData ni tekshirib, foydalanuvchi ma'lumotini qaytaradi.

    Returns: {"id": int, "first_name": str, "username": str, ...}
    Xato bo'lsa AuthError.
    """
    if not init_data:
        raise AuthError("init data yo'q")
    if not BOT_TOKEN:
        raise AuthError("BOT_TOKEN sozlanmagan")

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise AuthError("init data o'qib bo'lmadi")

    recv_hash = parsed.pop("hash", None)
    if not recv_hash:
        raise AuthError("hash yo'q")

    dcs = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recv_hash):
        raise AuthError("imzo mos kelmadi")

    # Muddat tekshiruvi — takroriy hujumdan (replay) himoya
    ttl = ttl or INITDATA_TTL
    if ttl > 0:
        try:
            auth_date = int(parsed.get("auth_date", "0"))
        except ValueError:
            auth_date = 0
        if auth_date <= 0:
            raise AuthError("auth_date yo'q")
        if time.time() - auth_date > ttl:
            raise AuthError("sessiya muddati tugadi — ilovani qayta oching")

    try:
        user = json.loads(parsed.get("user", "{}"))
    except Exception:
        raise AuthError("user maydoni buzuq")

    if not user.get("id"):
        raise AuthError("foydalanuvchi aniqlanmadi")
    return user
