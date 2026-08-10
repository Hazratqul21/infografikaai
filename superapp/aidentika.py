"""Aidentika API klienti — infografika/foto generatsiyasi.

Hujjat: https://docs.aidentika.com/api
  Base : https://api.aidentika.com/api/v1/public
  Auth : Authorization: Bearer ak_...
  Limit: 100 so'rov/daqiqa (429 + Retry-After), 5 rasm/so'rov, ~15 MB

Ishlash sxemasi ASINXRON:
  POST /generate/card -> {action_id} -> GET /status/{action_id} (yoki webhook)
  -> completed bo'lsa result_url

⚠️ Nega Idempotency-Key: tarmoq uzilib, biz so'rovni qayta yuborsak,
   kalitsiz Aidentika IKKI marta spark yechadi. Kalit 5 daqiqalik oynada
   takrorni to'sadi.
"""

import asyncio
import json
import uuid
from typing import Optional

import aiohttp

from superapp.config import (
    AIDENTIKA_BASE, AIDENTIKA_KEY, AIDENTIKA_TIMEOUT,
    AIDENTIKA_WEBHOOK_URL,
)

# Xato kodlari (docs.aidentika.com/api/errors) — bizga muhimlari
ERR_NO_BALANCE = "insufficient_tokens"   # 402 — spark tugagan
ERR_RATE = "rate_limit_exceeded"         # 429
ERR_BAD_KEY = "invalid_api_key"          # 401


class AidentikaError(Exception):
    """API xatosi — code bilan (chaqiruvchi qaror qabul qilishi uchun)."""

    def __init__(self, message: str, code: str = "", status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status


class AidentikaClient:
    """Yagona sessiyali klient (aiohttp ulanishi qayta ishlatiladi)."""

    def __init__(self, api_key: str = "", base: str = ""):
        self.api_key = api_key or AIDENTIKA_KEY
        self.base = (base or AIDENTIKA_BASE).rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def configured(self) -> bool:
        """Kalit bormi (kalitsiz butun modul o'chirilgan holatda ishlaydi)."""
        return bool(self.api_key)

    async def _sess(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=AIDENTIKA_TIMEOUT),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ────────────────────────── quyi qatlam ──────────────────────────

    async def _request(self, method: str, path: str, body: Optional[dict] = None,
                       idempotency_key: str = "", retries: int = 2) -> dict:
        """So'rov + 429 da Retry-After ni hurmat qilib qayta urinish.

        429 da ko'r-ko'rona qayta urinish limitni yanada chuqurlashtiradi,
        shuning uchun serverning aytgan muddatini kutamiz.
        """
        if not self.configured:
            raise AidentikaError("AIDENTIKA_KEY .env da yo'q", "no_key")

        sess = await self._sess()
        url = f"{self.base}{path}"
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if body is not None:
            headers["Content-Type"] = "application/json"

        last_err = None
        for attempt in range(retries + 1):
            try:
                async with sess.request(method, url, json=body,
                                        headers=headers or None) as r:
                    text = await r.text()
                    data = _safe_json(text)

                    if r.status == 200 or r.status == 201:
                        return data if isinstance(data, dict) else {"data": data}

                    code = ""
                    msg = ""
                    if isinstance(data, dict):
                        err = data.get("error")
                        if isinstance(err, dict):
                            code = err.get("code", "")
                            msg = err.get("message", "")
                        else:
                            code = data.get("code", "") or str(err or "")
                            msg = data.get("message", "") or str(err or "")

                    if r.status == 429 and attempt < retries:
                        wait = _retry_after(r.headers) or (2 ** attempt)
                        await asyncio.sleep(min(wait, 60))
                        last_err = AidentikaError(
                            msg or "rate limit", code or ERR_RATE, 429)
                        continue

                    raise AidentikaError(
                        msg or f"HTTP {r.status}", code, r.status)

            except asyncio.TimeoutError:
                last_err = AidentikaError("timeout", "timeout", 0)
                if attempt < retries:
                    await asyncio.sleep(1 + attempt)
                    continue
                raise last_err
            except aiohttp.ClientError as e:
                last_err = AidentikaError(str(e), "network", 0)
                if attempt < retries:
                    await asyncio.sleep(1 + attempt)
                    continue
                raise last_err

        raise last_err or AidentikaError("noma'lum xato")

    # ────────────────────────── biznes metodlar ──────────────────────────

    async def balance(self) -> dict:
        """Spark balansi — admin monitoringi uchun (tugab qolmasin)."""
        return await self._request("GET", "/balance")

    async def pricing(self) -> dict:
        """Amallar narxi (spark). Aidentika o'zgartirsa biz bilib turamiz."""
        return await self._request("GET", "/pricing")

    async def categories(self) -> dict:
        """Kategoriyalar va konsepsiyalar ro'yxati."""
        return await self._request("GET", "/categories")

    async def analyze(self, images: list, product_name: str = "") -> dict:
        """Rasmdan kategoriya/konsepsiyani aniqlash — BEPUL (spark yechilmaydi).

        Generatsiyadan oldin chaqiramiz: mijozdan kategoriya so'ramaymiz,
        bot o'zi aniqlaydi (Aidentikadan farqli ravishda — bizning UX ustunligimiz).
        """
        body = {"images": images}
        if product_name:
            body["product_name"] = product_name
        return await self._request("POST", "/analyze", body)

    async def generate_card(self, images: list, product_name: str = "",
                            category_id: str = "", concept_id: str = "",
                            design_reference: Optional[dict] = None,
                            creativity: Optional[float] = None,
                            project_id: Optional[str] = None,
                            wishes: str = "", description: str = "",
                            idempotency_key: str = "") -> dict:
        """Infografika kartochka (4 spark). -> {action_id, status, poll_url}

        design_reference — oldingi yoqqan kartochka. Shu bilan mijozning
        BARCHA tovarlari bir uslubda chiqadi (asosiy ustunligimiz).
        creativity: 0.0 = namunaga maksimal o'xshash ... 1.0 = erkin.
        wishes — "пожелания": uslub/rang/kompozitsiya bo'yicha erkin matn.

        ⚠️ `wishes`/`description` maydon nomlari hujjatdagi tavsifdan
        olingan; kalit kelgach jonli so'rov bilan TASDIQLASH kerak
        (nomi boshqacha bo'lsa faqat shu ikki qator o'zgaradi).
        """
        body: dict = {"images": images}
        if product_name:
            body["product_name"] = product_name
        if wishes:
            body["wishes"] = wishes
        if description:
            body["description"] = description
        if category_id:
            body["category_id"] = category_id
        if concept_id:
            body["concept_id"] = concept_id
        if design_reference:
            body["design_reference"] = design_reference
        if creativity is not None:
            body["creativity"] = max(0.0, min(1.0, float(creativity)))
        if project_id:
            body["project_id"] = project_id
        if AIDENTIKA_WEBHOOK_URL:
            body["webhook_url"] = AIDENTIKA_WEBHOOK_URL
        return await self._request(
            "POST", "/generate/card", body,
            idempotency_key=idempotency_key or str(uuid.uuid4()))

    async def generate_photo(self, images: list, product_name: str = "",
                             category_id: str = "", concept_id: str = "",
                             idempotency_key: str = "") -> dict:
        """Predmet fotosessiyasi (4 spark)."""
        body: dict = {"images": images}
        if product_name:
            body["product_name"] = product_name
        if category_id:
            body["category_id"] = category_id
        if concept_id:
            body["concept_id"] = concept_id
        if AIDENTIKA_WEBHOOK_URL:
            body["webhook_url"] = AIDENTIKA_WEBHOOK_URL
        return await self._request(
            "POST", "/generate/photo", body,
            idempotency_key=idempotency_key or str(uuid.uuid4()))

    async def edit(self, action_id: str, instruction: str,
                   idempotency_key: str = "") -> dict:
        """Tayyor natijani matn bilan tuzatish (2 spark)."""
        return await self._request(
            "POST", f"/edit/{action_id}", {"instruction": instruction},
            idempotency_key=idempotency_key or str(uuid.uuid4()))

    async def suggest_wishes(self, product_name: str = "",
                             category_id: str = "", images: Optional[list] = None) -> dict:
        """«AI идея» — sarlavha/tavsif/pojelaniyani AI o'zi taklif qiladi.

        Kuniga 100 ta bepul (keyin 20 so'rovga 1 spark), shuning uchun
        mijozdan ball YECHMAYMIZ.
        """
        body: dict = {}
        if product_name:
            body["product_name"] = product_name
        if category_id:
            body["category_id"] = category_id
        if images:
            body["images"] = images
        return await self._request("POST", "/wishes/suggest", body)

    async def status(self, action_id: str) -> dict:
        """Holat: pending / running / completed / failed."""
        return await self._request("GET", f"/status/{action_id}")

    async def cancel(self, action_id: str) -> dict:
        return await self._request("POST", f"/cancel/{action_id}")


def _safe_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text[:400]}


def _retry_after(headers) -> float:
    try:
        return float(headers.get("Retry-After", 0))
    except (TypeError, ValueError):
        return 0.0


def normalize_status(payload: dict) -> tuple:
    """Aidentika javobidan (status, result_url, error) ni ajratib olish.

    Javob shakli o'zgarsa — faqat SHU funksiya tuzatiladi.
    """
    status = str(payload.get("status", "")).lower()
    result = payload.get("result_url") or payload.get("resultUrl") or ""
    error = payload.get("error") or ""
    if isinstance(error, dict):
        error = error.get("message", "") or error.get("code", "")
    if status in ("completed", "success", "done"):
        return "completed", result, ""
    if status in ("failed", "error", "cancelled", "canceled"):
        return "failed", "", str(error or "generatsiya muvaffaqiyatsiz")
    return "running", "", ""
