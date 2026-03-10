"""kurs.uz aggregator — fetches rates for multiple banks at once.

Uses the kurs.uz AJAX API to get exchange rates for banks that we can't
scrape directly (no public page, Cloudflare-protected, JS-rendered, etc.).
One HTTP call per currency covers all banks.
"""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS
from db import get_session
from repos import BankRatesRepo

logger = logging.getLogger(__name__)

_API = "https://kurs.uz/ru/data/currencies"

# kurs.uz slug → our internal DB slug
# Only banks we DON'T have a dedicated collector for.
BANK_MAP: dict[str, str] = {
    "saderatbank": "saderatbank",
}


class KursUzCollector(BaseCollector):
    """Aggregator collector — fetches rates for multiple banks from kurs.uz."""

    slug = "kursuz"
    name = "kurs.uz Aggregator"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        # Unused — the multi-bank logic lives in collect().
        return []

    async def collect(self) -> int:
        """Override to save rates for every bank in BANK_MAP."""
        # {our_slug: {currency: (buy, sell)}}
        bank_rates: dict[str, list[tuple[str, float, float]]] = {}

        for currency in ("USD", "EUR", "RUB"):
            try:
                rows = await self.run_sync(_fetch_currency, currency)
            except Exception:
                logger.exception("kursuz: failed to fetch %s", currency)
                continue

            for kursuz_slug, buy, sell in rows:
                our_slug = BANK_MAP.get(kursuz_slug)
                if our_slug is None:
                    continue
                if buy > 0 and sell > 0:
                    bank_rates.setdefault(our_slug, []).append((currency, buy, sell))

        if not bank_rates:
            logger.warning("kursuz: no valid rates parsed")
            return 0

        saved = 0
        async with get_session() as session:
            repo = BankRatesRepo(session)
            for our_slug, rates in bank_rates.items():
                bank = await repo.get_bank_by_slug(our_slug)
                if not bank:
                    logger.error("kursuz: bank %s not found in DB", our_slug)
                    continue
                for code, buy, sell in rates:
                    await repo.add_rate(bank.id, code, buy, sell)
                    saved += 1

        logger.info("kursuz: saved %d rates for %d banks", saved, len(bank_rates))
        return saved


# ── sync helpers (run in executor) ───────────────────────────────────────


def _fetch_currency(currency: str) -> list[tuple[str, float, float]]:
    """Fetch one currency page from kurs.uz; return [(kursuz_slug, buy, sell)]."""
    resp = requests.get(
        _API,
        params={"by_bank": "all", "by_currency": currency, "sort_by": "sell"},
        headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
        timeout=20,
    )
    resp.raise_for_status()
    return _parse_table(resp.text)


_RATE_RE = re.compile(r"([\d\s]+)\s*сум")
_SLUG_RE = re.compile(r"/banks/([^/]+)/")


def _parse_table(html: str) -> list[tuple[str, float, float]]:
    """Parse kurs.uz HTML table fragment into (slug, buy, sell) triples."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, float, float]] = []

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        link = cells[0].find("a")
        if not link:
            continue
        href = link.get("href", "")
        slug_m = _SLUG_RE.search(href)
        if not slug_m:
            continue
        slug = slug_m.group(1)

        buy_m = _RATE_RE.search(cells[1].get_text())
        sell_m = _RATE_RE.search(cells[2].get_text())
        if not buy_m or not sell_m:
            continue

        try:
            buy = float(buy_m.group(1).replace(" ", ""))
            sell = float(sell_m.group(1).replace(" ", ""))
        except ValueError:
            continue

        results.append((slug, buy, sell))

    return results
