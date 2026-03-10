"""InFinBank — HTML table on exchange-rates page."""

import logging

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://www.infinbank.com/uz/private/exchange-rates/"

# Column mapping: table header has currency codes across the top row,
# rates in rows below.  Layout:
#   Row 0 (header): Valyuta | '' | USD | EUR | GBP | RUB | JPY | CHF
#   Row 1 (CB):     MB kurs | '' | ...
#   Row 2 (buy):    Ayrboshlash shoxobchasi | Olish | ...
#   Row 3 (sell):   Sotish | ...

# Currency positions (0-indexed in the header row, skipping first 2 cols)
_CUR_OFFSET = 2  # first two cells are labels


class InfinbankCollector(BaseCollector):
    slug = "infinbank"
    name = "InFinBank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        html = await self.run_sync(_fetch_html)
        return _parse(html)


def _fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse(html: str) -> list[tuple[str, float, float]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        logger.warning("infinbank: no table found")
        return []

    rows = table.find_all("tr")
    if len(rows) < 4:
        logger.warning("infinbank: expected >=4 rows, got %d", len(rows))
        return []

    # Parse header to find currency column indices
    header_cells = [c.get_text(strip=True).upper() for c in rows[0].find_all(["td", "th"])]
    cur_cols: dict[str, int] = {}
    for i, cell_text in enumerate(header_cells):
        if cell_text in CURRENCIES:
            cur_cols[cell_text] = i

    if not cur_cols:
        logger.warning("infinbank: no currency columns found in header")
        return []

    # Row 2 = buy (Olish), Row 3 = sell (Sotish)
    # Row 2 has an extra "Olish" label cell, Row 3 only has "Sotish" label
    # so sell columns are shifted left by 1 relative to header
    buy_cells = [c.get_text(strip=True) for c in rows[2].find_all(["td", "th"])]
    sell_cells = [c.get_text(strip=True) for c in rows[3].find_all(["td", "th"])]

    rates: list[tuple[str, float, float]] = []
    for code, col_idx in cur_cols.items():
        try:
            buy = float(buy_cells[col_idx].replace("\xa0", "").replace(" ", "").replace(",", ""))
            # Sell row has 1 fewer leading cell than buy row
            sell_idx = col_idx - (len(buy_cells) - len(sell_cells))
            sell = float(sell_cells[sell_idx].replace("\xa0", "").replace(" ", "").replace(",", ""))
        except (ValueError, IndexError):
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))

    return rates
