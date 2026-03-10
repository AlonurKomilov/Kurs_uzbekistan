"""Tengebank — JSON API collector."""

import logging

import requests

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://tengebank.uz/api/exchangerates/tables"


class TengebankCollector(BaseCollector):
    slug = "tengebank"
    name = "Tengebank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        data = await self.run_sync(_fetch)
        return _parse(data)


def _fetch() -> dict:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _parse(data: dict) -> list[tuple[str, float, float]]:
    personal = data.get("personal", [])
    if not personal:
        logger.warning("tengebank: no personal rates in API response")
        return []

    # First entry is the latest date
    latest = personal[0]
    currencies = latest.get("currency", {})

    rates: list[tuple[str, float, float]] = []
    for code, vals in currencies.items():
        if code not in CURRENCIES:
            continue
        try:
            buy = float(vals["buy"])
            sell = float(vals["sell"])
        except (KeyError, ValueError, TypeError):
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
    return rates
