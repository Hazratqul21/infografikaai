"""Kredit ↔ ball ko'prigi — Super App ning asosiy bot bilan YAGONA aloqasi.

Nega ko'prik kerak: mijozning hamyoni bitta bo'lishi kerak (kredit), lekin
infografika 1 kreditga arzimaydi. Shuning uchun mijoz kreditni ballarga
almashtiradi va kasr hisob superapp.db da yuritiladi.

⚠️ Asosiy DB sxemasi O'ZGARMAYDI. Faqat mavjud, sinovdan o'tgan
   `database.consume_credit()` / `add_credits()` chaqiriladi.
"""

import database as db
from config import logger
from superapp import store
from superapp.config import BALLS_PER_CREDIT


async def get_wallet(telegram_id: int) -> dict:
    """Mijozning to'liq hamyoni: kreditlar (slot) + ballar (generatsiya)."""
    credits = await db.get_credits(telegram_id)
    balls = await store.get_balls(telegram_id)
    return {
        "credits": credits,
        "balls": balls,
        "balls_per_credit": BALLS_PER_CREDIT,
        # Almashtirsa jami nechta ball bo'lishi mumkin (UI ko'rsatadi)
        "convertible_balls": credits * BALLS_PER_CREDIT,
    }


async def convert(telegram_id: int, credits: int = 1) -> dict:
    """Kreditni ballarga almashtirish.

    ⚠️ KOMPENSATSIYA: kredit yechilib, ball qo'shilmay qolsa — mijoz pulini
    yo'qotadi. Shuning uchun ball qo'shishda xato bo'lsa kreditni DARHOL
    qaytaramiz. Ikki xil DB (asosiy + superapp) o'rtasida umumiy tranzaksiya
    bo'lishi mumkin emas, shu sabab kompensatsiya yagona to'g'ri yechim.
    """
    if credits < 1:
        return {"ok": False, "error": "Kredit soni 1 dan kam bo'lishi mumkin emas"}

    took = await db.consume_credit(telegram_id, credits)
    if not took:
        have = await db.get_credits(telegram_id)
        return {"ok": False, "error": "Kredit yetarli emas", "credits": have}

    balls = credits * BALLS_PER_CREDIT
    try:
        new_balance = await store.add_balls(
            telegram_id, balls, "convert", f"credits:{credits}")
    except Exception as e:
        # Ball qo'shilmadi — kreditni qaytaramiz (mijoz zarar ko'rmasin)
        logger.error("Ball qo'shishda xato (user=%s): %s — kredit qaytarilmoqda",
                     telegram_id, e)
        try:
            await db.add_credits(telegram_id, credits)
        except Exception as e2:
            # Bu YOMON holat: kredit ham yo'q, ball ham yo'q. Baland ovozda
            # logga yozamiz — admin qo'lda tuzatishi uchun.
            logger.critical(
                "⛔️ KREDIT YO'QOLDI! user=%s credits=%s — QO'LDA QAYTARING. %s",
                telegram_id, credits, e2)
        return {"ok": False, "error": "Texnik xato, kredit qaytarildi"}

    logger.info("💱 user=%s: %s kredit -> %s ball (balans %s)",
                telegram_id, credits, balls, new_balance)
    return {"ok": True, "balls": new_balance, "added": balls}
