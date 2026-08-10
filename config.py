"""
Uzum Slot Bot — Konfiguratsiya

Barcha sozlamalar .env faylidan o'qiladi.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# .env faylni yuklash
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ─── Telegram Bot ───────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

# ─── Ma'lumotlar bazasi ─────────────────────────────────────────
DB_PATH: str = str(BASE_DIR / "bot_database.db")

# ─── Uzum API ───────────────────────────────────────────────────
UZUM_API_BASE: str = os.getenv("UZUM_API_BASE", "https://api-seller.uzum.uz")
UZUM_SELLER_URL: str = "https://seller.uzum.uz"
UZUM_LOGISTICS_URL: str = "https://logistics.uzum.uz"

# ─── Bot Seller Akkaunti (Sotrudnik/Xodim modeli) ───────────────
# Bot O'Z Uzum seller akkaunti bilan ishlaydi. Klientlar shu raqamni
# o'z kabinetlarida "Сотрудники" ga qo'shadi — keyin bot ularning
# do'konlarini bitta token orqali ko'radi va slot band qiladi.
UZUM_BOT_PHONE: str = os.getenv("UZUM_BOT_PHONE", "")          # masalan 998909572055
UZUM_BOT_PASSWORD: str = os.getenv("UZUM_BOT_PASSWORD", "")    # bo'lsa — parol-login
# Klientlarga ko'rsatiladigan raqam va rol (onboarding matni uchun)
UZUM_BOT_DISPLAY_PHONE: str = os.getenv("UZUM_BOT_DISPLAY_PHONE", "+998 90 957 20 55")
UZUM_STAFF_ROLE: str = os.getenv("UZUM_STAFF_ROLE", "Менеджер")
# Bot sessiyasi (JWT) shu faylda saqlanadi — restartda qayta login shart emas
UZUM_SESSION_FILE: str = str(BASE_DIR / "uzum_session.json")

# ─── KO'P AKKAUNT (SHARDING) — yukni bo'lish ───────────────────
# Akkaunt #1 = yuqoridagi mavjud UZUM_BOT_* (uzum_session.json — o'zgarmaydi).
# Qo'shimcha akkauntlar .env da raqamlangan: UZUM_BOT_PHONE_2 / _PASSWORD_2 /
# _DISPLAY_PHONE_2, UZUM_BOT_PHONE_3 ... Har biri alohida sessiya fayli
# (uzum_session_2.json ...). Faqat #1 bo'lsa — xatti-harakat AYNAN hozirgidek.
def _load_uzum_accounts() -> list:
    accts = []
    if UZUM_BOT_PHONE:
        accts.append({
            "id": "1", "phone": UZUM_BOT_PHONE, "password": UZUM_BOT_PASSWORD,
            "session_file": UZUM_SESSION_FILE, "display_phone": UZUM_BOT_DISPLAY_PHONE,
        })
    i = 2
    while os.getenv(f"UZUM_BOT_PHONE_{i}"):
        ph = os.getenv(f"UZUM_BOT_PHONE_{i}", "")
        accts.append({
            "id": str(i), "phone": ph,
            "password": os.getenv(f"UZUM_BOT_PASSWORD_{i}", ""),
            "session_file": str(BASE_DIR / f"uzum_session_{i}.json"),
            "display_phone": os.getenv(f"UZUM_BOT_DISPLAY_PHONE_{i}", ph),
        })
        i += 1
    return accts

UZUM_ACCOUNTS: list = _load_uzum_accounts()
# Yangi do'konlar shu akkauntga biriktiriladi (yukni bo'lish). Bo'sh bo'lsa —
# eng kam yuklangan akkaunt tanlanadi (DB dagi do'kon sonига qarab).
UZUM_NEW_SHOP_ACCOUNT: str = os.getenv("UZUM_NEW_SHOP_ACCOUNT", "")
# Bitta bot akkauntiga maksimal parallel so'rovlar (ban'dan saqlanish)
UZUM_MAX_CONCURRENCY: int = int(os.getenv("UZUM_MAX_CONCURRENCY", "8"))

# XAVFSIZLIK — Uzum rate-limit (429/503) javob bersa, BARCHA so'rovlar shu
# muddatga "sovish"ga (cooldown) o'tadi. Bu bo'lmasa bot limitga urilganda
# ham bir xil tezlikda urishda davom etadi va umumiy akkaunt ban bo'lishi
# mumkin (butun prod o'ladi). RATE_LIMIT_COOLDOWN=0 -> himoya O'CHIQ
# (eski xatti-harakat; kill-switch).
RATE_LIMIT_COOLDOWN: float = float(os.getenv("RATE_LIMIT_COOLDOWN", "5.0"))

# ⚠️ AUTH BO'RONI HIMOYASI (2026-08-01 log tahlilidan keyin qo'shildi).
# HODISA: 31-iyul 00:31–03:42 da token yangilanmay qoldi va HAR BIR so'rov
# qayta login qilishga urindi -> 3 soatda 17 698 ta OAuth urinishi (sekundiga
# ~5 ta) -> Uzum 429/503 qaytardi -> o'zimizni o'zimiz bloklab qo'ydik.
# Sabab: RATE_LIMIT_COOLDOWN faqat MA'LUMOT so'rovlarini qo'riqlaydi, OAuth
# yo'li esa semafordan ham, cooldown'dan ham chetlab o'tadi.
# YECHIM: login/refresh muvaffaqiyatsiz bo'lsa — eksponensial orqaga chekinish
# (5s, 10s, 20s ... AUTH_BACKOFF_MAX gacha). Kutish paytida mavjud token bilan
# ishlashda davom etamiz (ko'p hollarda u hali amal qiladi).
# AUTH_BACKOFF_BASE=0 -> himoya O'CHIQ (eski xatti-harakat; kill-switch).
AUTH_BACKOFF_BASE: float = float(os.getenv("AUTH_BACKOFF_BASE", "5.0"))
AUTH_BACKOFF_MAX: float = float(os.getenv("AUTH_BACKOFF_MAX", "300.0"))

# ⚡ NAKLADNOY RO'YXATI KESHI (do'kon bo'yicha) — 2026-08-02 da qo'shildi.
# MUAMMO: `get_invoices` (og'ir chaqiruv, ~480ms) HAR VAZIFA uchun alohida
# tortilardi. Bitta do'konda 6 ta vazifa bo'lsa — bir xil ro'yxat 6 marta.
# O'lchandi: 19 vazifa / 8 do'kon -> daqiqasiga 11 ta ORTIQCHA og'ir chaqiruv,
# semafor band bo'lib sikl 520ms dan 800ms ga cho'zilgan (slot poygasida
# yutqazish sababi). Slotlar uchun bunday kesh bor edi, nakladnoy uchun yo'q.
# YECHIM: do'kon bo'yicha kesh + lock (get_slots dagi kabi) -> O(vazifa) o'rniga
# O(do'kon). `max_age=0` bilan chaqirilsa kesh CHETLAB O'TILADI (yangi ma'lumot
# kerak bo'lgan joylar: bron holatini tasdiqlash, foydalanuvchi interfeysi).
# INVOICE_CACHE_TTL=0 -> kesh O'CHIQ (eski xatti-harakat; kill-switch).
INVOICE_CACHE_TTL: float = float(os.getenv("INVOICE_CACHE_TTL", "60"))

# SANA TAKLIFI — vazifa shuncha urinishdan keyin, agar belgilangan sanaga slot
# bo'lmasa-yu do'konda BOSHQA sanada bo'sh slot bo'lsa, foydalanuvchiga eng erta
# bo'sh slotni bir marta taklif qilamiz (tugma bilan). Silent 50k urinib refund
# o'rniga — mavjud slotni taklif. 0.5s interval → 300 urinish ≈ 5 daqiqa.
# SLOT_OFFER_AFTER_ATTEMPTS=0 -> taklif O'CHIQ (kill-switch).
SLOT_OFFER_AFTER_ATTEMPTS: int = int(os.getenv("SLOT_OFFER_AFTER_ATTEMPTS", "300"))

# TEZLIK / RAQOBAT — "issiq do'kon" adaptiv keshi. Do'konda MOS (band qilsa
# bo'ladigan) slot ko'rilsa — shu do'kon qisqa vaqtga "issiq" bo'ladi va
# HOT_SHOP_CACHE_TTL (tezroq) bilan pollanadi: raqobatchi eng ertani olib qo'ysa
# ("cannot be reserved"), biz keyingi ochilishni TEZ ilib olamiz. Faqat mos slot
# ko'rilgan do'kon issiq bo'ladi (sana-nomos do'konlar EMAS) — 503 xavfi past.
# HOT_SHOP_WINDOW=0 -> o'chiq (kill-switch, eski xatti-harakat).
HOT_SHOP_WINDOW: float = float(os.getenv("HOT_SHOP_WINDOW", "20"))     # necha sekund issiq
HOT_SHOP_CACHE_TTL: float = float(os.getenv("HOT_SHOP_CACHE_TTL", "0.3"))  # issiqda kesh TTL

# ─── Slot Tekshirish ────────────────────────────────────────────
# float — 0.5 (sekundiga 2 marta) ham mumkin. Uzum rate-limit qo'ymaydi
# (jonli test: 0.2s da ham 200). .env: CHECK_INTERVAL=0.5 -> tezroq.
CHECK_INTERVAL: float = float(os.getenv("CHECK_INTERVAL", "1"))
MAX_ATTEMPTS: int = 50000  # 24/7 uzluksiz ishlash uchun
REQUEST_TIMEOUT: int = 8  # API so'rov timeout (sekundlarda)

# TEZLIK — bir siklda nechta ENG-ERTA slotni ketma-ket urinish.
# Eng erta slot band ("cannot be reserved") bo'lsa — keyingi bo'sh slotga
# O'TADI (raqobatchi eng ertani olsa ham, biz ikkinchisini olamiz).
# BOOK_MAX_TRIES=1 -> eski xatti-harakat (faqat eng erta slot; kill-switch).
BOOK_MAX_TRIES: int = int(os.getenv("BOOK_MAX_TRIES", "4"))

# MIQYOS — Do'kon bo'yicha slot keshi.
# Bir do'konning bo'sh slotlari BARCHA nakladnoylari uchun bir xil (jonli
# tasdiqlangan). Shu sabab bir siklda bir do'kon uchun get_slots FAQAT BIR
# marta tortiladi; qolgan vazifalar keshdan oladi. Bu API yukni
# O(vazifalar) dan O(do'konlar) ga tushiradi — 1s tezlikni buzmasdan.
# TTL ~ CHECK_INTERVAL: har siklda yangilanadi, sikl ichida ulashiladi.
# SLOT_CACHE_TTL=0 -> kesh O'CHIQ (eski xatti-harakat, darhol qaytarish uchun).
SLOT_CACHE_TTL: float = float(os.getenv("SLOT_CACHE_TTL", "1.0"))

# MIQYOS — urinishlar hisoblagichini DB'ga BATCH yozish.
# Har vazifa har soniyada 'attempts' ni oshiradi; buni har safar DB'ga
# yozish o'rniga xotirada yig'ib, har ATTEMPTS_FLUSH_INTERVAL soniyada BIR
# marta (bitta tranzaksiyada) yoziladi. DB yozuv yukini ~20-50x kamaytiradi.
# 'attempts' — kritik bo'lmagan hisoblagich (MAX_ATTEMPTS + statistika), shu
# sabab kechikish/restartda ~interval'lik yo'qotish ahamiyatsiz.
# ATTEMPTS_FLUSH_INTERVAL=0 -> har safar yoziladi (eski xatti-harakat, kill-switch).
ATTEMPTS_FLUSH_INTERVAL: float = float(os.getenv("ATTEMPTS_FLUSH_INTERVAL", "20"))

# ─── Obuna Tizimlari ────────────────────────────────────────
MAX_FREE_TASKS: int = 1    # (eski) Bepul foydalanuvchi uchun max vazifalar
MAX_PREMIUM_TASKS: int = 10  # (eski) Premium foydalanuvchi uchun max vazifalar

# ─── Kredit Tizimi (1 kredit = 1 nakladnoy) ─────────────────
FREE_CREDITS: int = 5              # Yangi foydalanuvchiga bepul kreditlar
DEFAULT_CREDIT_PRICE: int = 20000  # 1 kredit narxi (admin o'zgartiradi — settings)
CREDIT_PRICE_KEY: str = "credit_price"  # settings jadvalidagi kalit

# ─── Payme (Paycom) To'lov Tizimi ──────────────────────────
PAYME_MERCHANT_ID: str = os.getenv("PAYME_MERCHANT_ID", "")
PAYME_SECRET_KEY: str = os.getenv("PAYME_SECRET_KEY", "")
SUBSCRIPTION_PRICE_UZS: int = int(os.getenv("SUBSCRIPTION_PRICE_UZS", "50000"))
PAYME_TEST_MODE: bool = os.getenv("PAYME_TEST_MODE", "True").lower() in ("true", "1", "yes")

# ─── Admin ──────────────────────────────────────────────────
# Qo'shimcha admin ID'lar (.env: ADMIN_IDS=111,222) + asosiy ADMIN_ID
_extra_admin_ids = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
    if x.strip().isdigit()
]
ADMIN_IDS: list = list({ADMIN_ID, *_extra_admin_ids})  # faqat .env dagi qat'iy ID'lar
# ESLATMA: username bo'yicha avtomatik admin berish OLIB TASHLANDI (xavfsizlik).
# Admin — faqat ADMIN_ID (va .env ADMIN_IDS). Quyidagi ro'yxat endi ishlatilmaydi.
ADMIN_USERNAMES: list = [
    u.strip().lower().lstrip("@")
    for u in os.getenv("ADMIN_USERNAMES", "Abduraufovx").split(",")
    if u.strip()
]

# ─── Logging ────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
)

logger = logging.getLogger("uzum_slot_bot")

# ─── Bot xabarlari (O'zbek tilida) ──────────────────────────────
MESSAGES = {
    "welcome": (
        "🟣 <b>Uzum Slot Bot</b> ga xush kelibsiz!\n\n"
        "Bu bot sizga Uzum Market da nakladnoy (yuk xati) uchun "
        "bo'sh slotlarni avtomatik topib, band qilib beradi.\n\n"
        "🔧 <b>Qanday ishlaydi:</b>\n"
        "1️⃣ Uzum kabinetingizdan API token oling\n"
        "2️⃣ Do'kon ID va Nakladnoy raqamini kiriting\n"
        "3️⃣ Bot 24/7 slot qidiradi va topishi bilan band qiladi\n\n"
        "📌 Boshlash uchun <b>«🔌 Do'konni ulash»</b> tugmasini bosing."
    ),

    "ask_token": (
        "🔑 <b>Uzum API Tokeningizni yuboring</b>\n\n"
        "Token olish yo'li:\n"
        "1. <a href='https://seller.uzum.uz'>seller.uzum.uz</a> ga kiring\n"
        "2. Sozlamalar → API Keys → <b>+ Создать ключ</b>\n"
        "3. Tokenni nusxalab shu yerga yuboring\n\n"
        "⚠️ Token faqat 1 marta ko'rsatiladi — "
        "darhol nusxalang!"
    ),

    "ask_shop_id": (
        "🏪 <b>Do'koningiz ID raqamini yuboring</b>\n\n"
        "🤔 <i>Buni qayerdan topaman?</i>\n"
        "1. <a href='https://seller.uzum.uz'>seller.uzum.uz</a> kabinetingizga kiring.\n"
        "2. <b>«Tovarlar» (Товары)</b> bo'limiga o'ting.\n"
        "3. Tepadagi ssilka (URL) ga qarang — u yerdagi raqam sizning do'koningiz ID'si hisoblanadi!\n\n"
        "👉 <b>Misol uchun:</b> Agar ssilka <i>seller.uzum.uz/seller/<b>15990</b>/products</i> bo'lsa, siz menga faqat <b>15990</b> deb yozib yuboring.\n\n"
        "📝 Qani, o'z ID raqamingizni kiriting:"
    ),

    "ask_nakladnoy": (
        "📦 <b>Endi Nakladnoy (ichki ID) raqamini yuboring</b>\n\n"
        "🤔 <i>Buni qayerdan topaman?</i>\n"
        "1. Kabinetingizdagi <b>«Поставки»</b> bo'limiga kiring.\n"
        "2. Kerakli nakladnoy (zayavka) ustiga bosing.\n"
        "3. Tepadagi ssilka (URL) dagi oxirgi raqamni oling!\n\n"
        "👉 <b>Misol uchun:</b> Agar ssilka <i>.../invoices/<b>3679697</b></i> bo'lsa, siz menga faqat <b>3679697</b> deb yozib yuboring.\n\n"
        "📝 Qani, nakladnoy raqamini kiriting:"
    ),

    "task_created": (
        "✅ <b>Vazifa yaratildi!</b>\n\n"
        "🏪 Do'kon ID: <code>{shop_id}</code>\n"
        "📦 Nakladnoy: <code>{nakladnoy}</code>\n\n"
        "🔄 Bot hozirdan boshlab har {interval} sekundda "
        "bo'sh slotlarni tekshiradi.\n\n"
        "Slot topilishi bilan sizga xabar beriladi! 🔔"
    ),

    "slot_found": (
        "🎉 <b>Slot band qilindi!</b>\n\n"
        "🏪 Do'kon: <code>{shop_id}</code>\n"
        "📦 Nakladnoy: <code>{nakladnoy}</code>\n"
        "📅 Sana: <b>{date}</b>\n"
        "⏰ Vaqt: <b>{time}</b>\n"
        "🏭 Ombor: <b>{warehouse}</b>\n\n"
        "Slot muvaffaqiyatli band qilindi. Yetkazib berishga "
        "o'z vaqtida tayyorlaning."
    ),

    "no_active_tasks": (
        "📋 Sizda hozircha faol vazifalar yo'q.\n\n"
        "Yangi vazifa yaratish uchun «➕ Yangi vazifa» "
        "tugmasini bosing."
    ),

    "token_saved": (
        "✅ <b>API Token saqlandi!</b>\n\n"
        "Endi vazifa yaratishingiz mumkin.\n"
        "«➕ Yangi vazifa» tugmasini bosing."
    ),

    "token_invalid": (
        "❌ <b>Token noto'g'ri ko'rinadi.</b>\n\n"
        "Iltimos, to'g'ri tokenni qayta yuboring.\n"
        "Token uzun matnli kalit bo'lishi kerak."
    ),

    "task_cancelled": (
        "🗑 Vazifa <b>#{task_id}</b> bekor qilindi."
    ),

    "registration_complete": (
        "✅ <b>Ro'yxatdan o'tish muvaffaqiyatli!</b>\n\n"
        "Endi «➕ Yangi vazifa» tugmasini bosib, "
        "slot qidirishni boshlashingiz mumkin."
    ),

    "error": (
        "⚠️ Xatolik yuz berdi: {error}\n"
        "Iltimos, qaytadan urinib ko'ring."
    ),

    "help": (
        "📖 <b>Yordam</b>\n\n"
        "🔹 /start — Botni qayta ishga tushirish\n"
        "🔹 /help — Ushbu yordam\n"
        "🔹 /status — Bot holati\n\n"
        "📌 <b>Asosiy tugmalar:</b>\n"
        "🔌 Do'konni ulash — do'konni botga ulash\n"
        "➕ Yangi vazifa — Slot qidirish vazifasini yaratish\n"
        "📋 Vazifalarim — Faol vazifalar ro'yxati\n"
        "❌ Vazifani bekor qilish — Vazifani to'xtatish\n\n"
        "💡 <b>Maslahat:</b> Bot 24/7 ishlaydi va bo'sh slot "
        "topilishi bilan sizga xabar beradi."
    ),

    "checking_status": (
        "📊 <b>Bot Holati</b>\n\n"
        "👤 Foydalanuvchilar: <b>{users_count}</b>\n"
        "📋 Faol vazifalar: <b>{active_tasks}</b>\n"
        "✅ Olingan slotlar: <b>{booked_slots}</b>\n"
        "🔄 Tekshirish intervali: <b>{interval} sek</b>\n\n"
        "⏱ Bot ishlayapti: <b>{uptime}</b>"
    ),
}
