"""Super App — mijoz uchun Mini App backend (FastAPI).

⚠️ ALOHIDA JARAYON: slot-superapp.service. `slot-bot` jarayoniga tegmaydi.
   Ishga tushirish: uvicorn superapp.api:app --host 127.0.0.1 --port 8100
"""

import asyncio
import hashlib
import hmac

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from config import logger
from superapp import credits, service, store
from superapp.auth import AuthError, verify_init_data
from superapp.config import (
    AIDENTIKA_WEBHOOK_SECRET, FREE_RETRIES, SUPERAPP_ENABLED,
)

app = FastAPI(title="INNASLOT Super App", version="0.1")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_poller: asyncio.Task = None


@app.on_event("startup")
async def _startup() -> None:
    await store.init()
    logger.info("Super App DB tayyor ✅")
    global _poller
    _poller = asyncio.create_task(service.poll_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _poller:
        _poller.cancel()
    await service.client().close()


# ─────────────────────────── Auth ───────────────────────────

async def current_user(x_telegram_init_data: str = Header(default="")) -> int:
    """Har so'rovda Telegram initData tekshiriladi (muddati bilan)."""
    try:
        user = verify_init_data(x_telegram_init_data)
    except AuthError as e:
        raise HTTPException(401, str(e))
    return int(user["id"])


# ─────────────────────────── Endpointlar ───────────────────────────

@app.get("/api/health")
async def health():
    return {"ok": True, "enabled": SUPERAPP_ENABLED,
            "generator": service.client().configured}


@app.get("/api/me")
async def me(uid: int = Depends(current_user)):
    """Hamyon + qisqa statistika (Mini App bosh ekrani)."""
    wallet = await credits.get_wallet(uid)
    gens = await store.list_generations(uid, limit=5)
    return {
        "wallet": wallet,
        # Qolgan bepul qayta generatsiyalar (Aidentikadagidek 3 ta)
        "free_retries": await store.free_retries_left(uid, FREE_RETRIES),
        "recent": gens,
        "open_jobs": await store.count_open_jobs(uid),
    }


@app.post("/api/convert")
async def convert(uid: int = Depends(current_user), body: dict = Body(...)):
    """Kreditni generatsiya ballariga almashtirish."""
    try:
        n = int(body.get("credits", 1))
    except (TypeError, ValueError):
        raise HTTPException(400, "credits noto'g'ri")
    if n < 1 or n > 100:
        raise HTTPException(400, "credits 1 dan 100 gacha bo'lsin")

    res = await credits.convert(uid, n)
    if not res.get("ok"):
        raise HTTPException(402, res.get("error", "Almashtirib bo'lmadi"))
    return res


@app.post("/api/generate/card")
async def generate_card(uid: int = Depends(current_user), body: dict = Body(...)):
    """Infografika kartochka generatsiyasini boshlash."""
    images = body.get("images") or []
    if not isinstance(images, list):
        raise HTTPException(400, "images ro'yxat bo'lishi kerak")
    try:
        return await service.start_card(
            telegram_id=uid,
            images=images,
            product_name=str(body.get("product_name", ""))[:200],
            category_id=str(body.get("category_id", "")),
            concept_id=str(body.get("concept_id", "")),
            use_style=bool(body.get("use_style", True)),
            wishes=str(body.get("wishes", ""))[:1000],
            description=str(body.get("description", ""))[:2000],
            parent_id=_int_or_none(body.get("parent_id")),
            # "Qayta yaratish" tugmasi — avval bepul limitdan oladi
            allow_free=bool(body.get("retry", False)),
        )
    except service.ServiceError as e:
        raise HTTPException(e.status, str(e))


def _int_or_none(v):
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


@app.post("/api/generation/{gen_id}/enhance")
async def enhance(gen_id: int, uid: int = Depends(current_user),
                  body: dict = Body(...)):
    """«Yaxshilash» — tayyor natijani matn bilan tuzatish."""
    try:
        return await service.enhance(uid, gen_id,
                                     str(body.get("instruction", ""))[:500])
    except service.ServiceError as e:
        raise HTTPException(e.status, str(e))


@app.post("/api/suggest")
async def suggest(uid: int = Depends(current_user), body: dict = Body(default={})):
    """«AI g'oya» — nom/tavsif/pojelaniya taklifi (bepul)."""
    try:
        return await service.suggest(
            uid,
            product_name=str(body.get("product_name", ""))[:200],
            category_id=str(body.get("category_id", "")),
        )
    except service.ServiceError as e:
        raise HTTPException(e.status, str(e))


@app.get("/api/generation/{gen_id}")
async def generation(gen_id: int, uid: int = Depends(current_user)):
    """Bitta generatsiya holati (Mini App shu yerni poll qiladi)."""
    gen = await store.get_generation(gen_id)
    if not gen:
        raise HTTPException(404, "topilmadi")
    if gen["telegram_id"] != uid:
        # Boshqa mijozning natijasi — mavjudligini ham oshkor qilmaymiz
        raise HTTPException(404, "topilmadi")
    if gen["status"] in ("pending", "running"):
        gen = await service.sync_generation(gen)
    return gen


@app.get("/api/generations")
async def generations(uid: int = Depends(current_user), limit: int = 30):
    return {"items": await store.list_generations(uid, limit=min(limit, 100))}


@app.get("/api/styles")
async def styles(uid: int = Depends(current_user)):
    return {"items": await store.list_styles(uid)}


@app.post("/api/styles")
async def add_style(uid: int = Depends(current_user), body: dict = Body(...)):
    """Yoqqan kartochkani uslub namunasi qilib saqlash.

    Shundan keyin mijozning barcha kartochkalari shu uslubda chiqadi.
    """
    url = str(body.get("source_url", "")).strip()
    if not url.startswith("https://"):
        raise HTTPException(400, "source_url https bo'lishi kerak")
    try:
        creativity = float(body.get("creativity", 0.3))
    except (TypeError, ValueError):
        creativity = 0.3
    sid = await store.save_style(
        uid, url, name=str(body.get("name", ""))[:60],
        creativity=max(0.0, min(1.0, creativity)))
    return {"ok": True, "id": sid}


# ─────────────────────────── Webhook ───────────────────────────

@app.post("/api/webhook/aidentika")
async def aidentika_webhook(request: Request,
                            x_signature: str = Header(default="")):
    """Aidentika generatsiya tugaganda chaqiradi (poll o'rniga — tezroq).

    ⚠️ Imzo tekshirilmasa istalgan odam soxta 'tayyor' yuborib, ballarni
    sarflangan qilib ko'rsatishi mumkin. HMAC-SHA256 MAJBURIY.
    """
    raw = await request.body()

    if AIDENTIKA_WEBHOOK_SECRET:
        calc = hmac.new(AIDENTIKA_WEBHOOK_SECRET.encode(), raw,
                        hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, (x_signature or "").strip()):
            logger.warning("Webhook imzosi mos kelmadi — rad etildi")
            raise HTTPException(401, "imzo noto'g'ri")
    else:
        # Sir sozlanmagan — webhook'ga ISHONMAYMIZ (poll baribir ishlaydi)
        logger.warning("AIDENTIKA_WEBHOOK_SECRET yo'q — webhook e'tiborsiz qoldirildi")
        return {"ok": True, "ignored": True}

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "json emas")

    action_id = str(payload.get("action_id", ""))
    if not action_id:
        return {"ok": True, "ignored": True}

    gen = await store.get_generation_by_action(action_id)
    if not gen:
        return {"ok": True, "ignored": True}

    # Webhook faqat "tekshir" signali — haqiqatni Aidentika'ning o'zidan
    # so'raymiz (soxta payload bilan holatni o'zgartirib bo'lmasin).
    await service.sync_generation(gen)
    return {"ok": True}
