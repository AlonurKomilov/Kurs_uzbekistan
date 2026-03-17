"""Ipoteka Bank — HTML scraper (<b>CODE</b> → sibling <td><span>)."""

import logging

import certifi
import httpx
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://www.ipotekabank.uz/private/services/currency/"


class IpotekaCollector(BaseCollector):
    slug = "ipoteka"
    name = "Ipoteka Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        import ssl
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        async with httpx.AsyncClient(timeout=20.0, verify=ssl_ctx, follow_redirects=True) as client:
            resp = await client.get(URL, headers=HEADERS)
            resp.raise_for_status()
        return _parse(resp.text)


def _parse(html: str) -> list[tuple[str, float, float]]:
    """Parse Ipoteka currency table: <table class='currency-table'>
    Row columns: [currency_name+code, buy, sell, cb_rate].
    Currency code is embedded in the cell text (e.g. 'AQSH DollariUSD')."""
    soup = BeautifulSoup(html, "html.parser")
    rates: list[tuple[str, float, float]] = []
    seen: set[str] = set()

    table = soup.find("table", class_="currency-table")
    if not table:
        logger.warning("ipoteka: currency-table not found")
        return []

    for row in table.find_all("tr")[1:]:  # skip header
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        # Detect currency code from cell text
        cell_text = cols[0].get_text(strip=True).upper()
        code = None
        for cur in CURRENCIES:
            if cur in cell_text:
                code = cur
                break
        if not code or code in seen:
            continue
        try:
            buy = float(cols[1].get_text(strip=True).replace(" ", "").replace(",", ""))
            sell = float(cols[2].get_text(strip=True).replace(" ", "").replace(",", ""))
        except ValueError:
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
            seen.add(code)
    return rates
