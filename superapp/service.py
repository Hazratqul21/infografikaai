"""Infografika xizmati — hold → generatsiya → natija → commit/refund.

Bu yerda pul mantiqi jamlangan. Asosiy qoida:
  MIJOZ HECH QACHON NATIJASIZ BALL YO'QOTMASLIGI KERAK.

Shuning uchun har generatsiya hold bilan boshlanadi va faqat natija
tasdiqlanganda commit qilinadi; xato/timeout bo'lsa ballar qaytariladi.
"""

import asyncio
import uuid
from typing import Optional

from config import logger
from superapp import store
from superapp.aidentika import AidentikaClient, AidentikaError, normalize_status
from superapp.config import (
    BALL_COST, FREE_RETRIES, HOLD_TTL, MAX_CONCURRENT_JOBS, SUPERAPP_ENABLED,
)

# Yagona klient (aiohttp ulanishi qayta ishlatiladi)
_client: Optional[AidentikaClient] = None


def client() -> AidentikaClient:
    global _client
    if _client is None:
        _client = AidentikaClient()
    return _client


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


async def start_card(telegram_id: int, images: list, product_name: str = "",
                     category_id: str = "", concept_id: str = "",
                     use_style: bool = True, wishes: str = "",
                     description: str = "", parent_id: Optional[int] = None,
                     allow_free: bool = False) -> dict:
    """Infografika generatsiyasini boshlash.

    Tartib (tartib MUHIM):
      1. tekshiruvlar (modul yoqiqmi, kalit bormi, parallel limit)
      2. HOLD — ballarni ushlash (yoki bepul qayta generatsiya)
      3. Aidentika'ga so'rov
      4. so'rov yiqilsa — hold DARHOL qaytariladi

    allow_free — "qayta generatsiya" tugmasi: avval bepul limitdan oladi
    (Aidentikadagidek 3 ta), tugagach oddiy ball yechiladi.
    """
    if not SUPERAPP_ENABLED:
        raise ServiceError("Modul vaqtincha o'chirilgan", 503)
    if not client().configured:
        raise ServiceError("Generatsiya xizmati sozlanmagan", 503)
    if not images:
        raise ServiceError("Rasm yuborilmadi", 400)
    if len(images) > 5:
        raise ServiceError("Bir so'rovda ko'pi bilan 5 ta rasm", 400)

    open_jobs = await store.count_open_jobs(telegram_id)
    if open_jobs >= MAX_CONCURRENT_JOBS:
        raise ServiceError(
            f"Sizda {open_jobs} ta generatsiya navbatda — tugashini kuting", 429)

    # Bepul qayta generatsiya bo'lsa — ball ushlanmaydi
    is_free = False
    hold_id = None
    if allow_free and await store.take_free_retry(telegram_id, FREE_RETRIES):
        is_free = True
    else:
        hold_id = await store.create_hold(telegram_id, BALL_COST["card"], "card")
        if hold_id is None:
            raise ServiceError("Ball yetarli emas — kredit almashtiring", 402)

    gen_id = await store.create_generation(
        telegram_id, "card", hold_id, product_name, category_id, concept_id,
        wishes=wishes, description=description, parent_id=parent_id,
        is_free=is_free)

    # Uslub xotirasi — mijozning oldingi yoqqan kartochkasi namuna bo'ladi
    design_ref = None
    creativity = None
    if use_style:
        st = await store.get_default_style(telegram_id)
        if st and st.get("source_url"):
            design_ref = {"url": st["source_url"]}
            creativity = st.get("creativity")

    try:
        res = await client().generate_card(
            images=images,
            product_name=product_name,
            category_id=category_id,
            concept_id=concept_id,
            design_reference=design_ref,
            creativity=creativity,
            wishes=wishes,
            description=description,
            # Idempotency: bitta generatsiya yozuvi = bitta kalit. Tarmoq
            # uzilib qayta yuborilsa ham Aidentika ikki marta yechmaydi.
            idempotency_key=f"gen-{gen_id}-{uuid.uuid4().hex[:8]}",
        )
    except AidentikaError as e:
        # So'rov ketmadi — ballarni DARHOL qaytaramiz
        await _release(hold_id)
        await store.finish_generation(gen_id, "failed", error=str(e))
        logger.warning("Aidentika xatosi (user=%s, gen=%s): %s [%s]",
                       telegram_id, gen_id, e, e.code)
        raise ServiceError(_human_error(e), _http_for(e))
    except Exception as e:
        await _release(hold_id)
        await store.finish_generation(gen_id, "failed", error=str(e))
        logger.error("Generatsiya boshlanmadi (user=%s): %s", telegram_id, e)
        raise ServiceError("Texnik xato — ballar qaytarildi", 500)

    action_id = str(res.get("action_id") or "")
    if not action_id:
        await _release(hold_id)
        await store.finish_generation(gen_id, "failed", error="action_id yo'q")
        raise ServiceError("Xizmat noto'g'ri javob qaytardi — ballar qaytarildi", 502)

    await store.attach_action(gen_id, action_id)
    logger.info("🎨 Generatsiya boshlandi: user=%s gen=%s action=%s",
                telegram_id, gen_id, action_id)
    return {"id": gen_id, "action_id": action_id, "status": "pending"}


async def enhance(telegram_id: int, gen_id: int, instruction: str) -> dict:
    """«Улучшение» — tayyor natijani matn bilan tuzatish (arzonroq).

    Aidentika'ning `/edit/{action_id}` metodi: rasm qayta yuborilmaydi,
    oldingi natija ustida ishlaydi.
    """
    if not SUPERAPP_ENABLED:
        raise ServiceError("Modul vaqtincha o'chirilgan", 503)
    instruction = (instruction or "").strip()
    if len(instruction) < 3:
        raise ServiceError("Nima o'zgartirishni yozing", 400)

    parent = await store.get_generation(gen_id)
    if not parent or parent["telegram_id"] != telegram_id:
        raise ServiceError("Topilmadi", 404)
    if parent["status"] != "completed" or not parent.get("action_id"):
        raise ServiceError("Faqat tayyor natijani yaxshilash mumkin", 400)

    hold_id = await store.create_hold(telegram_id, BALL_COST["edit"], "edit")
    if hold_id is None:
        raise ServiceError("Ball yetarli emas — kredit almashtiring", 402)

    new_id = await store.create_generation(
        telegram_id, "edit", hold_id,
        product_name=parent.get("product_name") or "",
        wishes=instruction, parent_id=gen_id)

    try:
        res = await client().edit(
            parent["action_id"], instruction,
            idempotency_key=f"edit-{new_id}-{uuid.uuid4().hex[:8]}")
    except AidentikaError as e:
        await _release(hold_id)
        await store.finish_generation(new_id, "failed", error=str(e))
        raise ServiceError(_human_error(e), _http_for(e))
    except Exception as e:
        await _release(hold_id)
        await store.finish_generation(new_id, "failed", error=str(e))
        raise ServiceError("Texnik xato — ballar qaytarildi", 500)

    action_id = str(res.get("action_id") or "")
    if not action_id:
        await _release(hold_id)
        await store.finish_generation(new_id, "failed", error="action_id yo'q")
        raise ServiceError("Xizmat noto'g'ri javob qaytardi — ballar qaytarildi", 502)

    await store.attach_action(new_id, action_id)
    logger.info("✏️ Yaxshilash boshlandi: user=%s gen=%s (asos %s)",
                telegram_id, new_id, gen_id)
    return {"id": new_id, "action_id": action_id, "status": "pending"}


async def suggest(telegram_id: int, product_name: str = "",
                  category_id: str = "") -> dict:
    """«AI идея» — nom/tavsif/pojelaniya taklifi. Mijozdan ball YECHILMAYDI."""
    if not client().configured:
        raise ServiceError("Xizmat sozlanmagan", 503)
    try:
        return await client().suggest_wishes(product_name=product_name,
                                             category_id=category_id)
    except AidentikaError as e:
        raise ServiceError(_human_error(e), _http_for(e))


async def _release(hold_id: Optional[int]) -> None:
    """Hold bo'lsa qaytarish (bepul generatsiyada hold bo'lmaydi)."""
    if hold_id:
        await store.resolve_hold(hold_id, ok=False)


async def sync_generation(gen: dict) -> dict:
    """Bitta generatsiya holatini Aidentika'dan yangilash.

    Idempotent: `resolve_hold` allaqachon yakunlangan hold'ga ta'sir qilmaydi,
    shuning uchun webhook va poll bir vaqtda kelsa ham ball ikki marta
    yechilmaydi/qaytarilmaydi.
    """
    action_id = gen.get("action_id")
    if not action_id:
        return gen

    try:
        payload = await client().status(action_id)
    except AidentikaError as e:
        # Vaqtinchalik xato — hold'ga tegmaymiz, keyingi siklda qayta uriladi.
        # (Osilib qolsa `expire_holds` baribir qaytaradi.)
        logger.debug("status olinmadi (action=%s): %s", action_id, e)
        return gen

    status, result_url, error = normalize_status(payload)
    if status == "running":
        return gen

    if status == "completed":
        await store.finish_generation(gen["id"], "completed", result_url=result_url)
        if gen.get("hold_id"):
            await store.resolve_hold(gen["hold_id"], ok=True)
        logger.info("✅ Generatsiya tayyor: gen=%s", gen["id"])
    else:
        await store.finish_generation(gen["id"], "failed", error=error)
        if gen.get("hold_id"):
            await store.resolve_hold(gen["hold_id"], ok=False)
        logger.info("↩️ Generatsiya muvaffaqiyatsiz, ballar qaytarildi: gen=%s (%s)",
                    gen["id"], error)

    return await store.get_generation(gen["id"]) or gen


async def poll_loop(interval: float = 10.0) -> None:
    """Fon tsikli: tugallanmagan generatsiyalarni tekshiradi + hold tozalaydi.

    Webhook ishlasa bu deyarli bekorga aylanadi — lekin webhook yetib
    kelmasligi mumkin, shuning uchun poll ZAXIRA sifatida doim ishlaydi.
    """
    logger.info("🔄 Super App poll tsikli ishga tushdi (har %ss)", interval)
    while True:
        try:
            for gen in await store.list_open_generations():
                await sync_generation(gen)
                await asyncio.sleep(0.2)      # Aidentika limitini hurmat qilamiz
            freed = await store.expire_holds(HOLD_TTL)
            if freed:
                logger.warning("⏱ %s ta osilib qolgan hold qaytarildi", freed)
        except Exception as e:
            logger.error("Poll tsikli xatosi: %s", e, exc_info=True)
        await asyncio.sleep(interval)


def _human_error(e: AidentikaError) -> str:
    """Mijozga tushunarli xabar (texnik kod emas)."""
    return {
        "insufficient_tokens": "Xizmat balansi tugagan — admin bilan bog'laning",
        "invalid_api_key": "Xizmat sozlamasida xato — admin bilan bog'laning",
        "rate_limit_exceeded": "Hozir navbat band — bir daqiqadan keyin urining",
        "image_too_large": "Rasm juda katta (15 MB dan kichik bo'lsin)",
        "timeout": "Xizmat javob bermadi — qayta urining",
        "network": "Tarmoq xatosi — qayta urining",
    }.get(e.code, "Generatsiya boshlanmadi — ballar qaytarildi")


def _http_for(e: AidentikaError) -> int:
    """Aidentika xatosini o'z HTTP kodimizga o'girish."""
    if e.code == "insufficient_tokens":
        return 503        # BIZNING balans tugagan — mijozning aybi emas
    if e.code == "rate_limit_exceeded":
        return 429
    if e.code == "image_too_large":
        return 413
    return 502
