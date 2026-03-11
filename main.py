"""
kurs_uz_bot — single-process entry point.

Starts:
  1. Telegram bot (aiogram polling)
  2. Rate collectors (APScheduler interval)
  3. Daily digest (APScheduler cron)
  4. Old-data cleanup (APScheduler cron, daily)
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

# ── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("kurs_uz_bot")

# ── Optional Sentry ─────────────────────────────────────────────────────

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)


# ── Collectors registry ─────────────────────────────────────────────────

def _build_collectors():
    from collectors.aab import AabCollector
    from collectors.agrobank import AgrobankCollector
    from collectors.aloqabank import AloqabankCollector
    from collectors.cbu import CbuCollector
    from collectors.hamkorbank import HamkorbankCollector
    from collectors.infinbank import InfinbankCollector
    from collectors.ipoteka import IpotekaCollector
    from collectors.ipakyuli import IpakyuliCollector
    from collectors.kapitalbank import KapitalbankCollector
    from collectors.kdbbank import KdbbankCollector
    from collectors.nbu import NbuCollector
    from collectors.ofb import OfbCollector
    from collectors.poytaxtbank import PoytaxtbankCollector
    from collectors.sqb import SqbCollector
    from collectors.tbc import TbcCollector
    from collectors.tengebank import TengebankCollector
    from collectors.trastbank import TrastbankCollector
    from collectors.turonbank import TuronbankCollector
    from collectors.universalbank import UniversalbankCollector
    from collectors.xalqbank import XalqbankCollector

    return [
        CbuCollector(),
        KapitalbankCollector(),
        NbuCollector(),
        IpotekaCollector(),
        HamkorbankCollector(),
        TbcCollector(),
        TuronbankCollector(),
        AloqabankCollector(),
        TrastbankCollector(),
        PoytaxtbankCollector(),
        KdbbankCollector(),
        AabCollector(),
        AgrobankCollector(),
        InfinbankCollector(),
        OfbCollector(),
        SqbCollector(),
        XalqbankCollector(),
        TengebankCollector(),
        UniversalbankCollector(),
        IpakyuliCollector(),
    ]


async def run_collectors():
    """Run all collectors concurrently."""
    collectors = _build_collectors()
    results = await asyncio.gather(
        *(c.collect() for c in collectors), return_exceptions=True
    )
    for c, r in zip(collectors, results):
        if isinstance(r, Exception):
            logger.error("Collector %s failed: %s", c.slug, r)
        else:
            logger.info("Collector %s: %d rates", c.slug, r)


async def run_digest_morning(bot: Bot):
    from bot.digest import send_digest

    await send_digest(bot, "morning")
    await send_digest(bot, "twice")


async def run_digest_evening(bot: Bot):
    from bot.digest import send_digest

    await send_digest(bot, "evening")
    await send_digest(bot, "twice")


async def run_cleanup():
    from db import get_session
    from repos import BankRatesRepo

    async with get_session() as session:
        repo = BankRatesRepo(session)
        deleted = await repo.delete_older_than(settings.RETENTION_DAYS)
        logger.info("Cleanup: deleted %d old rates", deleted)


# ── Main ────────────────────────────────────────────────────────────────

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Register middleware + handlers
    from bot.handlers import router
    from bot.middlewares import DbMiddleware, I18nMiddleware

    dp.message.middleware(DbMiddleware())
    dp.callback_query.middleware(DbMiddleware())
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())
    dp.include_router(router)

    # Scheduler
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    # Collect rates every N minutes
    scheduler.add_job(
        run_collectors,
        IntervalTrigger(minutes=settings.COLLECTION_INTERVAL_MINUTES),
        id="collectors",
        replace_existing=True,
    )

    # Morning digest at 09:00 Tashkent
    scheduler.add_job(
        run_digest_morning,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="digest_morning",
        replace_existing=True,
    )

    # Evening digest at 18:00 Tashkent
    scheduler.add_job(
        run_digest_evening,
        CronTrigger(hour=18, minute=0),
        args=[bot],
        id="digest_evening",
        replace_existing=True,
    )

    # Daily cleanup at 03:00
    scheduler.add_job(
        run_cleanup,
        CronTrigger(hour=3, minute=0),
        id="cleanup",
        replace_existing=True,
    )

    scheduler.start()

    # Initial collection on startup
    logger.info("Running initial rate collection...")
    await run_collectors()

    logger.info("Bot starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
