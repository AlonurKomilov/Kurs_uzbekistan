"""Trustbank — HTML table scraper (exchange-box__table)."""

import logging

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://trustbank.uz/en/services/exchange-rates/"


class TrustbankCollector(BaseCollector):
    slug = "trustbank"
    name = "Trustbank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        html = await self.run_sync(_fetch_html)
        return _parse(html)


def _fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse(html: str) -> list[tuple[str, float, float]]:
    soup = BeautifulSoup(html, "html.parser")
    rates: list[tuple[str, float, float]] = []
    seen: set[str] = set()

    table = soup.find("table", class_="exchange-box__table")
    if not table:
        logger.warning("trustbank: exchange-box__table not found")
        return []

    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        code = cols[0].get_text(strip=True).upper()
        if code not in CURRENCIES or code in seen:
            continue
        values: list[float] = []
        for col in cols[1:]:
            val_div = col.find("div", class_="exchange-box__value")
            if not val_div:
                continue
            span = val_div.find("span")
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
