"""Orient Finance Bank — rates embedded in homepage HTML (rate widget)."""

import logging
import re

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://ofb.uz/uz/"


class OfbCollector(BaseCollector):
    slug = "ofb"
    name = "Orient Finance Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        html = await self.run_sync(_fetch_html)
        return _parse(html)


def _fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse(html: str) -> list[tuple[str, float, float]]:
    soup = BeautifulSoup(html, "html.parser")

    # Find the rate widget section: contains text like
    # "ValyutaUSDSotish12200Sotib olish12100"
    widget = None
    for el in soup.find_all(class_=re.compile(r"rate", re.I)):
        text = el.get_text(strip=True)
        if "USD" in text and "EUR" in text:
            widget = el
            break

    if not widget:
        logger.warning("ofb: rate widget not found")
        return []

    # The widget text is a flat string like:
    # "OFB Valyutalar kursiValyutaUSDSotish12200Sotib olish12100ValyutaEURSotish15300.00Sotib olish13300.00..."
    text = widget.get_text(separator="|", strip=True)

    rates: list[tuple[str, float, float]] = []
    # Pattern: ValyutaCODESotishSELLSotib olishBUY
    for m in re.finditer(
        r"(?:Valyuta)?\s*([A-Z]{3})\s*\|?\s*Sotish\s*\|?\s*([\d.,]+)\s*\|?\s*Sotib olish\s*\|?\s*([\d.,]+)",
        text,
    ):
        code = m.group(1).upper()
        if code not in CURRENCIES:
            continue
        try:
            sell = float(m.group(2).replace(",", "").replace(" ", ""))
            buy = float(m.group(3).replace(",", "").replace(" ", ""))
        except ValueError:
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))

    return rates
