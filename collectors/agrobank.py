"""Agrobank — JSON API (CMS currency-rates block)."""

import logging

import httpx

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://agrobank.uz/api/v1/?action=pages&code=uz/person&lang=uz"


class AgrobankCollector(BaseCollector):
    slug = "agrobank"
    name = "Agrobank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(URL, headers={**HEADERS, "Accept": "application/json"})
            resp.raise_for_status()
        return _parse(resp.json())


def _parse(data: dict) -> list[tuple[str, float, float]]:
    if not data.get("success"):
        logger.warning("agrobank: API returned success=false")
        return []

    # Walk sections to find the currency-rates block
    sections = data.get("data", {}).get("sections", [])
    for section in sections:
        for block in section.get("blocks", []):
            if block.get("type") != "currency-rates":
                continue
            items = block.get("content", {}).get("items", [])
            rates: list[tuple[str, float, float]] = []
            for item in items:
                code = item.get("alpha3", "").upper()
                if code not in CURRENCIES:
                    continue
                try:
                    buy = float(item["buy"])
                    sell = float(item["sale"])
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug("agrobank: failed to parse %s: %s", code, e)
                    continue
                if buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
            return rates

    logger.warning("agrobank: currency-rates block not found")
    return []
