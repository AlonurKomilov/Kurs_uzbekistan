"""
Universal Bank Exchange Rates Collector

STATUS: UNAVAILABLE
Universal Bank does not publish exchange rates on their website.
Investigation findings (2025-01-10):
- Website: https://universalbank.uz
- Checked pages: /currency/, /en/currency/, /branches
- API endpoints tested: /api/currencies (returns currency list only, no rates)
- Result: NO EXCHANGE RATES PUBLISHED ONLINE

This collector is kept for future re-evaluation if the bank starts publishing rates.
"""

import asyncio
import logging
from typing import List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

async def collect():
    """Main collection function - DISABLED (no rates available)."""
    logger.warning("⚠️ Universal Bank: Exchange rates NOT AVAILABLE online")
    logger.info("ℹ️ Universal Bank does not publish exchange rates on their website")
    logger.info("ℹ️ Checked: /currency/, /en/currency/, API endpoints")
    logger.info("ℹ️ This collector is disabled until rates become available")
    return 0


if __name__ == "__main__":
    asyncio.run(collect())
