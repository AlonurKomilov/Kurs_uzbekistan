"""Daily digest: build message per language → batch-send to subscribers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from db import get_session
from repos import BankRatesRepo, ChannelSubRepo, UserRepo

logger = logging.getLogger(__name__)

BATCH_SIZE = 25
BATCH_DELAY = 1.0  # seconds between batches (Telegram allows ~30 msgs/sec)
CONCURRENCY = 5    # parallel sends within a batch


def _get_i18n():
    """Access the shared I18nMiddleware instance for rendering locale strings."""
    from bot.middlewares import I18nMiddleware
    return I18nMiddleware()


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
    i18n_mw = _get_i18n()
    i18n = lambda key, **kw: i18n_mw.get_text(lang, key, **kw)
    date_str = datetime.now().strftime("%d.%m.%Y")
    lines = [i18n("digest.title"), i18n("digest.date", date=date_str), ""]
    for code in ("USD", "EUR", "RUB"):
        if code in rates:
            lines.append(i18n(f"digest.{code.lower()}", rate=f"{rates[code]:,.0f}"))
    lines.append(i18n("digest.footer"))
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
        sem = asyncio.Semaphore(CONCURRENCY)

        async def _send_one(uid: int) -> None:
            async with sem:
                try:
                    await bot.send_message(uid, text)
                    stats["sent"] += 1
                except TelegramForbiddenError:
                    stats["blocked"] += 1
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

        for i in range(0, len(user_ids), BATCH_SIZE):
            batch = user_ids[i : i + BATCH_SIZE]
            await asyncio.gather(*(_send_one(uid) for uid in batch))
            await asyncio.sleep(BATCH_DELAY)

    logger.info(
        "digest(%s): sent=%d failed=%d blocked=%d",
        schedule, stats["sent"], stats["failed"], stats["blocked"],
    )
    return stats


async def post_to_channels(bot: Bot, schedule: str = "morning") -> dict[str, int]:
    """Post current rates to all subscribed channels/groups for given schedule."""
    stats = {"sent": 0, "failed": 0}

    rates = await _get_cbu_rates()
    if not rates:
        logger.warning("channel post: no CBU rates")
        return stats

    async with get_session() as session:
        repo = ChannelSubRepo(session)
        subs = await repo.get_by_schedule(schedule)

    for sub in subs:
        text = _render(sub.lang, rates)
        text += "\n\n🤖 @kurs_uzbekistan_bot"
        try:
            await bot.send_message(sub.chat_id, text)
            stats["sent"] += 1
            logger.info("channel post: sent to %s (%s)", sub.title, sub.chat_id)
        except TelegramForbiddenError:
            # Bot was removed from channel — clean up
            logger.warning("channel post: bot removed from %s, deleting sub", sub.chat_id)
            async with get_session() as s:
                await ChannelSubRepo(s).remove(sub.chat_id)
                await s.commit()
            stats["failed"] += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(sub.chat_id, text)
                stats["sent"] += 1
            except Exception:
                stats["failed"] += 1
        except Exception as exc:
            logger.error("channel post to %s failed: %s", sub.chat_id, exc)
            stats["failed"] += 1

    if subs:
        logger.info(
            "channel posts(%s): sent=%d failed=%d",
            schedule, stats["sent"], stats["failed"],
        )
    return stats
