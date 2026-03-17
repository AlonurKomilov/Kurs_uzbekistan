"""Hamkorbank — JSON API (rates ÷ 100, filter destination_code=2)."""

import logging

import httpx

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

API_URL = "https://api-dbo.hamkorbank.uz/webflow/v1/exchanges"


class HamkorbankCollector(BaseCollector):
    slug = "hamkorbank"
    name = "Hamkorbank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        headers = {**HEADERS, "Accept": "application/json", "Referer": "https://hamkorbank.uz/"}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(API_URL, headers=headers)
            resp.raise_for_status()
        return _parse(resp.json())


def _parse(data) -> list[tuple[str, float, float]]:
    exchanges: list = []
    if isinstance(data, dict):
        for key in ("data", "rates", "exchanges", "result"):
            if key in data:
                exchanges = data[key]
                break
    elif isinstance(data, list):
        exchanges = data

    rates: list[tuple[str, float, float]] = []
    seen: set[str] = set()
    for item in exchanges:
        code = (item.get("currency_char") or "").upper()
        if code not in CURRENCIES or code in seen:
            continue
        if item.get("destination_code") != "2":
            continue
        try:
            buy = float(item["buying_rate"]) / 100.0
            sell = float(item["selling_rate"]) / 100.0
        except (KeyError, ValueError, TypeError) as e:
            logger.debug("hamkorbank: failed to parse %s: %s", code, e)
            continue
        if 0 < buy < 1_000_000 and 0 < sell < 1_000_000:
            rates.append((code, buy, sell))
            seen.add(code)
    return rates
