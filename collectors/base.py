"""Base collector ABC — all bank collectors inherit from this."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from db import get_session
from repos import BankRatesRepo

logger = logging.getLogger(__name__)

CURRENCIES = {"USD", "EUR", "RUB"}

# Common browser-like headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}


class BaseCollector(ABC):
    slug: ClassVar[str]
    name: ClassVar[str]

    @abstractmethod
    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        """Return list of (code, buy, sell). Only CURRENCIES are kept."""
        ...

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def collect(self) -> int:
        """Fetch rates and persist to DB. Returns count saved."""
        try:
            raw = await self.fetch_rates()
        except Exception:
            logger.exception("%s: fetch failed", self.slug)
            return 0

        rates = [(c, b, s) for c, b, s in raw if c in CURRENCIES and b > 0 and s > 0]
        if not rates:
            logger.warning("%s: no valid rates", self.slug)
            return 0

        async with get_session() as session:
            repo = BankRatesRepo(session)
            bank = await repo.get_bank_by_slug(self.slug)
            if not bank:
                logger.error("%s: bank not found in DB", self.slug)
                return 0
            saved = 0
            for code, buy, sell in rates:
                await repo.add_rate(bank.id, code, buy, sell)
                saved += 1
            logger.info("%s: saved %d rates", self.slug, saved)
            return saved

    # Helper: run sync HTTP call in executor (for requests-based collectors)
    @staticmethod
    async def run_sync(fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn, *args)
