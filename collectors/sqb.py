"""SQB (Sanoat Qurilish Bank) — JSON API collector."""

import logging

import requests

from collectors.base import BaseCollector, CURRENCIES, HEADERS

logger = logging.getLogger(__name__)

URL = "https://sqb.uz/api/site-kurs-api/"

# Currency code mapping (API uses ISO alpha-3)
CODE_MAP = {"USD": "USD", "EUR": "EUR", "RUB": "RUB"}


class SqbCollector(BaseCollector):
    slug = "sqb"
    name = "SQB"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        data = await self.run_sync(_fetch)
        return _parse(data)


def _fetch() -> dict:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _parse(data: dict) -> list[tuple[str, float, float]]:
    # Prefer "online" section (clean values), fall back to "offline" (values in hundredths)
    online = {item["code"]: item for item in data.get("data", {}).get("online", [])}
    offline = {item["code"]: item for item in data.get("data", {}).get("offline", [])}

    rates: list[tuple[str, float, float]] = []
    for code in CURRENCIES:
        if code in online:
            item = online[code]
            try:
                buy = float(item["buy"])
                sell = float(item["sell"])
            except (KeyError, ValueError, TypeError):
                continue
        elif code in offline:
            item = offline[code]
            try:
                buy = float(item["buy"]) / 100
                sell = float(item["sell"]) / 100
            except (KeyError, ValueError, TypeError):
                continue
        else:
            continue
        if buy > 0 and sell > 0:
            rates.append((code, buy, sell))
    return rates
