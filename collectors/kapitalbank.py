"""Kapitalbank — Playwright-based collector (Cloudflare bypass).

kapitalbank.uz is behind Cloudflare Bot Management.  Plain HTTP gives 403.
Playwright with anti-detection flags successfully loads the page.
Exchange rates page: /uz/services/exchange-rates/
Widget class: .kapitalbank_currency_container
"""

from __future__ import annotations

import logging

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

_URL = "https://kapitalbank.uz/uz/services/exchange-rates/"

# Maps Uzbek text to currency codes
_CURRENCY_MAP = {
    "USD": "USD",
    "EUR": "EUR",
    "RUB": "RUB",
}

_WANTED = {"USD", "EUR", "RUB"}


class KapitalbankCollector(BaseCollector):
    slug = "kapitalbank"
    name = "Kapitalbank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        from browser_pool import get_browser

        browser = await get_browser()
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        try:
            page = await ctx.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            resp = await page.goto(_URL, wait_until="domcontentloaded", timeout=30000)
            if resp is None or resp.status != 200:
                logger.warning("kapitalbank: HTTP %s", resp.status if resp else "no response")
                return []

            await page.wait_for_selector(".kapitalbank_currency_container", timeout=10000)
            container = await page.query_selector(".kapitalbank_currency_container")
            if not container:
                logger.warning("kapitalbank: currency container not found")
                return []

            text = await container.inner_text()
        finally:
            try:
                await page.close()
            except Exception:
                pass
            await ctx.close()

        return _parse_widget(text)


def _parse_widget(text: str) -> list[tuple[str, float, float]]:
    """Parse the widget text where each value is on a separate line.

    Pattern (repeating):
        USD
        Sotish
        12195
        Sotib olish
        12100
        0,0
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    rates: list[tuple[str, float, float]] = []
    seen: set[str] = set()

    # Find the "Valyutalar kursi" section — rates start after "Filiallarda" or after
    # the tab labels. We look for currency code followed by Sotish/Sotib olish pattern.
    i = 0
    while i < len(lines) - 4:
        code = lines[i].upper()
        if (
            code in _WANTED
            and code not in seen
            and i + 4 < len(lines)
            and lines[i + 1].lower() == "sotish"
            and lines[i + 3].lower() == "sotib olish"
        ):
            try:
                sell = float(lines[i + 2].replace(" ", "").replace("\xa0", ""))
                buy = float(lines[i + 4].replace(" ", "").replace("\xa0", ""))
            except ValueError:
                i += 1
                continue
            if buy > 0 and sell > 0:
                rates.append((code, buy, sell))
                seen.add(code)
            i += 5  # skip past this block
        else:
            i += 1

    if not rates:
        logger.warning("kapitalbank: no rates parsed from widget text")
    return rates
