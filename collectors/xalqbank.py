"""Xalqbank (Xalq banki) — JSON API collector."""

import logging

import requests

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://xb.uz/api/v1/external/client/default?_f=json&_l=uz&destination=2"

# ISO numeric code → ISO alpha-3
_NUM_TO_ALPHA = {"840": "USD", "978": "EUR", "643": "RUB"}


class XalqbankCollector(BaseCollector):
    slug = "xalqbank"
    name = "Xalqbank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        data = await self.run_sync(_fetch)
        return _parse(data)


def _fetch() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _parse(data: list[dict]) -> list[tuple[str, float, float]]:
    rates: list[tuple[str, float, float]] = []
    for item in data:
        code_num = str(item.get("CODE", ""))
        code = _NUM_TO_ALPHA.get(code_num)
        if code is None or code not in CURRENCIES:
            continue
        try:
            buy = float(item["BUYING_RATE"])
            sell = float(item["SELLING_RATE"])
        except (KeyError, ValueError, TypeError):
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
    return rates
