"""Shared Playwright browser singleton to avoid cold-start per collection."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_playwright = None
_browser = None


async def get_browser():
    """Return a shared Chromium browser instance, launching if needed."""
    global _playwright, _browser
    async with _lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright
            if _playwright is not None:
                try:
                    await _playwright.stop()
                except Exception as e:
                    logger.warning("Error stopping playwright: %s", e)
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            logger.info("Playwright browser launched")
    return _browser


async def close():
    """Shut down shared browser and Playwright."""
    global _playwright, _browser
    async with _lock:
        if _browser is not None:
            try:
                await _browser.close()
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            _browser = None
        if _playwright is not None:
            try:
                await _playwright.stop()
            except Exception as e:
                logger.warning("Error stopping playwright: %s", e)
            _playwright = None
