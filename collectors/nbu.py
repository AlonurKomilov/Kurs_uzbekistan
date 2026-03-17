"""NBU — National Bank of Uzbekistan (HTML scraper)."""

import logging

import httpx
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://nbu.uz/en/for-individuals-exchange-rates/"


class NbuCollector(BaseCollector):
    slug = "nbu"
    name = "National Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(URL, headers=HEADERS)
            resp.raise_for_status()
        return _parse(resp.text)


def _parse(html: str) -> list[tuple[str, float, float]]:
    soup = BeautifulSoup(html, "html.parser")
    options = soup.find_all("option", attrs={"data-buy": True, "data-sell": True})

    rates: list[tuple[str, float, float]] = []
    seen: set[str] = set()
    for opt in options:
        code = (opt.get("value") or "").upper()
        if code not in CURRENCIES or code in seen:
            continue
        buy_s = str(opt.get("data-buy", "")).replace(" ", "").replace(",", "")
        sell_s = str(opt.get("data-sell", "")).replace(" ", "").replace(",", "")
        if not buy_s or not sell_s or buy_s == "-" or sell_s == "-":
            continue
        try:
            buy, sell = float(buy_s), float(sell_s)
        except ValueError:
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
            seen.add(code)
    return rates
