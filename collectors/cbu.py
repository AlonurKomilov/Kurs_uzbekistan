"""CBU — Central Bank of Uzbekistan (JSON API, async httpx)."""

import logging

import httpx

from collectors.base import BaseCollector, CURRENCIES

logger = logging.getLogger(__name__)

CBU_URL = "https://cbu.uz/oz/arkhiv-kursov-valyut/json/"


class CbuCollector(BaseCollector):
    slug = "cbu"
    name = "Central Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(CBU_URL)
            resp.raise_for_status()
            data = resp.json()

        rates: list[tuple[str, float, float]] = []
        for row in data:
            code = (row.get("Ccy") or "").upper()
            if code not in CURRENCIES:
                continue
            try:
                rate = float(row["Rate"])
            except (KeyError, ValueError, TypeError) as e:
                logger.debug("cbu: failed to parse rate for %s: %s", code, e)
                continue
            if rate > 0:
                rates.append((code, rate, rate))  # CBU: buy == sell
        return rates
