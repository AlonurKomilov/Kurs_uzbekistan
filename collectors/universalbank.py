"""Universal Bank — JSON API collector."""

import logging

import httpx

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://universalbank.uz/api/currencies/daily?locale=uz"

# ISO numeric code → ISO alpha-3
_NUM_TO_ALPHA = {"840": "USD", "978": "EUR", "643": "RUB"}


class UniversalbankCollector(BaseCollector):
    slug = "universalbank"
    name = "Universal Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(URL, headers=HEADERS)
            resp.raise_for_status()
        return _parse(resp.json())


def _parse(data: dict) -> list[tuple[str, float, float]]:
    items = data.get("items", [])
    if not items:
        logger.warning("universalbank: no items in API response")
        return []

    rates: list[tuple[str, float, float]] = []
    for item in items:
        code = _NUM_TO_ALPHA.get(str(item.get("code", "")))
        if code is None or code not in CURRENCIES:
            continue
        try:
            buy = float(item["buyingRate"])
            sell = float(item["sellingRate"])
        except (KeyError, ValueError, TypeError) as e:
            logger.debug("universalbank: failed to parse %s: %s", code, e)
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
    return rates
