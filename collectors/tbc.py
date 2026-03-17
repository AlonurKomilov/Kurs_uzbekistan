"""TBC Bank — hybrid JSON/HTML scraper."""

import logging

import httpx
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://tbcbank.uz/currencies/"


class TbcCollector(BaseCollector):
    slug = "tbc"
    name = "TBC Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        headers = {**HEADERS, "Accept": "application/json, text/html, */*"}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(URL, headers=headers)
            resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        if "json" in ct:
            try:
                return _parse_json(resp.json())
            except ValueError:
                pass
        return _parse_html(resp.text)


def _parse_json(data: dict) -> list[tuple[str, float, float]]:
    items = data.get("data", data.get("rates", [data])) if isinstance(data, dict) else [data]
    rates: list[tuple[str, float, float]] = []
    for item in items:
        code = None
        for k in ("code", "currency", "ccy"):
            if k in item:
                code = str(item[k]).upper()
                break
        if not code or code not in CURRENCIES:
            continue
        buy = sell = None
        for k in ("buy", "buying", "buyRate"):
            if k in item:
                buy = float(item[k])
                break
        for k in ("sell", "selling", "sellRate"):
            if k in item:
                sell = float(item[k])
                break
        if buy is None and sell is None:
            for k in ("rate", "value"):
                if k in item:
                    buy = sell = float(item[k])
                    break
        if buy and sell and buy > 0 and sell > 0:
            rates.append((code, buy, sell))
    return rates


def _parse_html(html: str) -> list[tuple[str, float, float]]:
    """Parse TBC grid-based table:
    tr.table-grid rows, first td = code (e.g. 'USD'),
    td.col-start-4 span = sell, td.col-start-5 span = buy."""
    soup = BeautifulSoup(html, "html.parser")
    rates: list[tuple[str, float, float]] = []
    for row in soup.find_all("tr", class_="table-grid"):
        cells = row.find_all("td")
        if not cells:
            continue
        code = cells[0].get_text(strip=True).upper()
        if code not in CURRENCIES:
            continue
        # Find buy (col-start-5) and sell (col-start-4) cells
        buy_val = sell_val = None
        for cell in cells:
            cls = " ".join(cell.get("class", []))
            text = cell.get_text(strip=True).replace(",", "").replace(" ", "")
            if "col-start-4" in cls:
                try:
                    sell_val = float(text)
                except ValueError:
                    pass
            elif "col-start-5" in cls:
                try:
                    buy_val = float(text)
                except ValueError:
                    pass
        if buy_val and sell_val and buy_val > 0 and sell_val > 0:
            rates.append((code, buy_val, sell_val))
    return rates
