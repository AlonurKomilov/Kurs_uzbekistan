"""Ipak Yoli Bank — Playwright-based collector.

The ipakyulibank.uz homepage renders a currency widget client-side (Nuxt/Vue).
Plain HTTP returns HTML but the rate numbers are injected by JS.
CSS selector: .currency-table with data-test attributes.
"""

from __future__ import annotations

import logging

from collectors.base import BaseCollector, CURRENCIES

logger = logging.getLogger(__name__)

_URL = "https://ipakyulibank.uz/"

# Maps Uzbek currency names to ISO codes
_NAME_TO_CODE = {
    "aqsh dollar": "USD",
    "dollar": "USD",
    "yevro": "EUR",
    "rossiya rubli": "RUB",
    "rubl": "RUB",
}


class IpakyuliCollector(BaseCollector):
    slug = "ipakyulibank"
    name = "Ipak Yo'li Bank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            try:
                ctx = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = await ctx.new_page()
                await page.goto(_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".currency-table", timeout=15000)

                rows = await page.query_selector_all(".currency-row")
                rates: list[tuple[str, float, float]] = []
                seen: set[str] = set()

                for row in rows:
                    name_el = await row.query_selector("[data-test='currency-name']")
                    buy_el = await row.query_selector("[data-test='currency-buy']")
                    sell_el = await row.query_selector("[data-test='currency-sell']")
                    if not name_el or not buy_el or not sell_el:
                        continue

                    name_text = (await name_el.inner_text()).strip().lower()
                    buy_text = (await buy_el.inner_text()).strip().replace(" ", "").replace("\xa0", "")
                    sell_text = (await sell_el.inner_text()).strip().replace(" ", "").replace("\xa0", "")

                    # Resolve currency code from name
                    code = None
                    for key, val in _NAME_TO_CODE.items():
                        if key in name_text:
                            code = val
                            break
                    if not code or code not in CURRENCIES or code in seen:
                        continue

                    try:
                        buy = float(buy_text)
                        sell = float(sell_text)
                    except ValueError:
                        continue
                    if buy > 0 and sell > 0:
                        rates.append((code, buy, sell))
                        seen.add(code)
            finally:
                await browser.close()

        if not rates:
            logger.warning("ipakyulibank: no rates parsed from currency-table")
        return rates
