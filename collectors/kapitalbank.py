"""Kapitalbank — currently blocked by Cloudflare.

The kapitalbank.uz domain uses Cloudflare Bot Management (JS challenge)
which prevents scraping with plain HTTP requests. This collector is
disabled until an API or alternative endpoint becomes available.
"""

import logging

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class KapitalbankCollector(BaseCollector):
    slug = "kapitalbank"
    name = "Kapitalbank"

    async def fetch_rates(self) -> list[tuple[str, float, float]]:
        logger.info("kapitalbank: skipped — site is behind Cloudflare challenge")
        return []
