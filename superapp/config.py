"""Super App — konfiguratsiya (.env dan).

Barcha yangi imkoniyatlar kill-switch bilan: redeploysiz, faqat .env +
servis restarti bilan o'chiriladi.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ─── Alohida ma'lumotlar bazasi ─────────────────────────────────
# ⚠️ Botning bot_database.db si EMAS. Generatsiya tarixi, ballar va
# hold'lar shu yerda — asosiy DB'ga yozuv yuki tushmasin.
SUPERAPP_DB: str = str(BASE_DIR / "superapp.db")

# ─── Aidentika API ──────────────────────────────────────────────
AIDENTIKA_BASE: str = os.getenv(
    "AIDENTIKA_BASE", "https://api.aidentika.com/api/v1/public")
AIDENTIKA_KEY: str = os.getenv("AIDENTIKA_KEY", "")
AIDENTIKA_TIMEOUT: int = int(os.getenv("AIDENTIKA_TIMEOUT", "30"))
# Webhook — Aidentika tayyor bo'lganda o'zi chaqiradi (poll o'rniga).
# Bo'sh bo'lsa faqat poll ishlaydi (webhook ixtiyoriy).
AIDENTIKA_WEBHOOK_URL: str = os.getenv("AIDENTIKA_WEBHOOK_URL", "")
AIDENTIKA_WEBHOOK_SECRET: str = os.getenv("AIDENTIKA_WEBHOOK_SECRET", "")

# Aidentika narxlari (spark). Ular o'zgarsa — GET /pricing dan yangilanadi,
# bular faqat zaxira qiymatlar.
SPARK_COST = {
    "card": 4,
    "photo": 4,
    "edit": 2,
    "video_5": 16,
    "video_10": 32,
}

# ─── Ball (generatsiya birligi) iqtisodi ────────────────────────
# ⚠️ Asosiy DB dagi `users.credits` BUTUN son bo'lib qoladi (migratsiya YO'Q).
# Mijoz 1 kreditni ballarga almashtiradi, kasr hisob shu yerda yuritiladi.
BALLS_PER_CREDIT: int = int(os.getenv("BALLS_PER_CREDIT", "4"))
# Har amal necha ball turadi (mijoz ko'radigan narx)
BALL_COST = {
    "card": int(os.getenv("BALL_COST_CARD", "1")),
    "photo": int(os.getenv("BALL_COST_PHOTO", "1")),
    "edit": int(os.getenv("BALL_COST_EDIT", "1")),
}
# Har mijozga bepul qayta generatsiya (Aidentika modeli — 3 ta)
FREE_RETRIES: int = int(os.getenv("SUPERAPP_FREE_RETRIES", "3"))

# ─── Xavfsizlik / limitlar ──────────────────────────────────────
# Telegram initData ning yaroqlilik muddati (soniya). Bu bo'lmasa o'g'irlangan
# initData abadiy ishlayveradi (mavjud admin panelidagi kamchilik).
INITDATA_TTL: int = int(os.getenv("INITDATA_TTL", "86400"))
# Bitta mijoz bir vaqtda nechta generatsiya boshlashi mumkin
MAX_CONCURRENT_JOBS: int = int(os.getenv("SUPERAPP_MAX_JOBS", "3"))
# Hold shuncha soniyadan keyin avtomatik qaytariladi (osilib qolgan vazifa)
HOLD_TTL: int = int(os.getenv("SUPERAPP_HOLD_TTL", "900"))  # 15 daqiqa

# ─── KILL-SWITCH ────────────────────────────────────────────────
# 0 -> butun infografika moduli o'chadi (API 503 qaytaradi).
SUPERAPP_ENABLED: bool = os.getenv("SUPERAPP_ENABLED", "1") not in ("0", "false", "False")
