"""KDB Bank Uzbekistan — marquee ticker parser."""

import logging
import re

import requests

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://kdb.uz/currency/"


class KdbbankCollector(BaseCollector):
    slug = "kdbbank"
    name = "KDB Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        html = await self.run_sync(_fetch_html)
        return _parse(html)


def _fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse(html: str) -> list[tuple[str, float, float]]:
    """Parse KDB marquee ticker: 'USD | UZS12191.2512100/12250'
    Format: CODE | UZS<cb_rate><buy>/<sell>"""
    rates: list[tuple[str, float, float]] = []
    # Match pattern: CODE ... buy/sell
    for m in re.finditer(
        r"(USD|EUR|RUB)\s*\|\s*UZS.*?(\d[\d.]+)/(\d[\d.]+)",
        html,
    ):
        code = m.group(1).upper()
        if code not in CURRENCIES:
            continue
        try:
            buy = float(m.group(2))
            sell = float(m.group(3))
        except ValueError:
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
    return rates
