"""Daily digest: build message per language → batch-send to subscribers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from db import get_session
from repos import BankRatesRepo, UserRepo

logger = logging.getLogger(__name__)

BATCH_SIZE = 25
BATCH_DELAY = 1.0  # seconds between batches (Telegram allows ~30 msgs/sec)

TEMPLATES: dict[str, dict[str, str]] = {
    "uz_cy": {
        "title": "📈 Кунлик валюта курси",
        "date": "📅 {date}",
        "usd": "💵 АҚШ доллари: {rate} сўм",
        "eur": "💶 Евро: {rate} сўм",
        "rub": "🇷🇺 Рубль: {rate} сўм",
        "footer": "\n🔄 Манба: МБ",
    },
    "ru": {
        "title": "📈 Ежедневный курс валют",
        "date": "📅 {date}",
        "usd": "💵 USD: {rate} сум",
        "eur": "💶 EUR: {rate} сум",
        "rub": "🇷🇺 RUB: {rate} сум",
        "footer": "\n🔄 Источник: ЦБ РУз",
    },
    "en": {
        "title": "📈 Daily Currency Rates",
        "date": "📅 {date}",
        "usd": "💵 USD: {rate} som",
        "eur": "💶 EUR: {rate} som",
        "rub": "🇷🇺 RUB: {rate} som",
        "footer": "\n🔄 Source: CBU",
    },
}


async def _get_cbu_rates() -> dict[str, float]:
    """Fetch latest CBU rates (buy==sell) for USD/EUR/RUB."""
    async with get_session() as session:
        repo = BankRatesRepo(session)
        result: dict[str, float] = {}
        for code in ("USD", "EUR", "RUB"):
            rates = await repo.latest_by_code(code)
            # Find the CBU entry
            for r in rates:
                if r.bank.slug == "cbu":
                    result[code] = float(r.sell)
                    break
        return result


def _render(lang: str, rates: dict[str, float]) -> str:
    t = TEMPLATES.get(lang, TEMPLATES["en"])
    date_str = datetime.now().strftime("%d.%m.%Y")
    lines = [t["title"], t["date"].format(date=date_str), ""]
    for code in ("USD", "EUR", "RUB"):
        if code in rates:
            lines.append(t[code.lower()].format(rate=f"{rates[code]:,.0f}"))
    lines.append(t["footer"])
    return "\n".join(lines)


async def send_digest(bot: Bot, schedule: str = "morning") -> dict[str, int]:
    """Send digest to all subscribers for given schedule. Returns stats."""
    stats = {"sent": 0, "failed": 0, "blocked": 0}

    rates = await _get_cbu_rates()
    if not rates:
        logger.warning("digest: no CBU rates available")
        return stats

    async with get_session() as session:
        user_repo = UserRepo(session)
        groups = await user_repo.get_subscribers_by_schedule(schedule)

    for lang, user_ids in groups.items():
        text = _render(lang, rates)
        for i in range(0, len(user_ids), BATCH_SIZE):
            batch = user_ids[i : i + BATCH_SIZE]
            for uid in batch:
                try:
                    await bot.send_message(uid, text)
                    stats["sent"] += 1
                except TelegramForbiddenError:
                    stats["blocked"] += 1
                    # Auto-unsubscribe blocked users
                    async with get_session() as s:
                        await UserRepo(s).soft_unsubscribe(uid)
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try:
                        await bot.send_message(uid, text)
                        stats["sent"] += 1
                    except Exception:
                        stats["failed"] += 1
                except (TelegramBadRequest, Exception):
                    stats["failed"] += 1
            await asyncio.sleep(BATCH_DELAY)

    logger.info(
        "digest(%s): sent=%d failed=%d blocked=%d",
        schedule, stats["sent"], stats["failed"], stats["blocked"],
    )
    return stats
