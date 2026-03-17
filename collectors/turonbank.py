"""Turonbank — HTML table scraper (exchange-value → span)."""

import logging

import httpx
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://turonbank.uz/en/services/exchange-rates/"


class TuronbankCollector(BaseCollector):
    slug = "turonbank"
    name = "Turonbank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(URL, headers=HEADERS)
            resp.raise_for_status()
        return _parse(resp.text)


def _parse(html: str) -> list[tuple[str, float, float]]:
    """Parse Turonbank exchange table: table.exchange__table.
    First col has div.currency-name__code with the code.
    Other cols have div.exchange-value > span with the rate value."""
    soup = BeautifulSoup(html, "html.parser")
    rates: list[tuple[str, float, float]] = []
    seen: set[str] = set()

    # Use the first table (main retail rates)
    table = soup.find("table", class_="exchange__table")
    if not table:
        logger.warning("turonbank: exchange__table not found")
        return []

    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        # Currency code from div.currency-name__code
        code_div = cols[0].find("div", class_="currency-name__code")
        if not code_div:
            continue
        code = code_div.get_text(strip=True).upper()
        if code not in CURRENCIES or code in seen:
            continue
        # Extract buy/sell from exchange-value spans
        values: list[float] = []
        for col in cols[1:]:
            ex_div = col.find("div", class_="exchange-value")
            if not ex_div:
                continue
            span = ex_div.find("span")
            if not span:
                continue
            try:
                val = float(span.get_text(strip=True).replace(" ", "").replace(",", ""))
            except ValueError:
                continue
            if 0 < val < 1_000_000:
                values.append(val)
        if len(values) >= 2:
            rates.append((code, values[0], values[1]))
            seen.add(code)
    return rates
