"""Asia Alliance Bank — JSON embedded in homepage (Rates = {...})."""

import json
import logging
import re

import requests

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://aab.uz/uz/"


class AabCollector(BaseCollector):
    slug = "aab"
    name = "Asia Alliance Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        html = await self.run_sync(_fetch_html)
        return _parse(html)


def _fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


_RATES_RE = re.compile(r"Rates\s*=\s*(\{.+?\})\s*;?\s*\n")


def _parse(html: str) -> list[tuple[str, float, float]]:
    m = _RATES_RE.search(html)
    if not m:
        logger.warning("aab: Rates JS variable not found")
        return []

    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        logger.warning("aab: failed to parse Rates JSON")
        return []

    # Use BANK channel (physical exchange office rates)
    bank = data.get("BANK", {})
    buy_map = bank.get("BUY", {})
    sell_map = bank.get("SALE", {})

    rates: list[tuple[str, float, float]] = []
    for code in CURRENCIES:
        b = buy_map.get(code)
        s = sell_map.get(code)
        if b is None or s is None:
            continue
        try:
            buy = float(str(b).replace(" ", ""))
            sell = float(str(s).replace(" ", ""))
        except ValueError:
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))

    return rates
