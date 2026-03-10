"""Agrobank — JSON API (CMS currency-rates block)."""

import logging

import requests

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://agrobank.uz/api/v1/?action=pages&code=uz/person&lang=uz"


class AgrobankCollector(BaseCollector):
    slug = "agrobank"
    name = "Agrobank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        data = await self.run_sync(_fetch_json)
        return _parse(data)


def _fetch_json() -> dict:
    resp = requests.get(URL, headers={**HEADERS, "Accept": "application/json"}, timeout=20)
    resp.raise_for_status()
    return resp.json()


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
                except (KeyError, ValueError, TypeError):
                    continue
                if buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
            return rates

    logger.warning("agrobank: currency-rates block not found")
    return []
