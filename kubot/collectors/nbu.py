"""
National Bank of Uzbekistan (NBU) Exchange Rates Collector

Collects exchange rates from NBU's official website.
Uses requests library for reliable HTTP handling.
"""

import asyncio
import logging
from typing import List, Tuple
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from core.repos import BankRatesRepo
from infrastructure.db import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "GBP", "JPY", "CHF", "KRW", "CNY"]

NBU_CONFIG = {
    "name": "National Bank of Uzbekistan",
    "slug": "nbu",
    "url": "https://nbu.uz/en/for-individuals-exchange-rates/",
    "website": "https://nbu.uz"
}


def fetch_html_sync() -> str:
    """Fetch NBU HTML page using requests library (sync)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        'Connection': 'keep-alive',
    }
    
    response = requests.get(NBU_CONFIG["url"], headers=headers, timeout=20)
    response.raise_for_status()
    logger.info(f"✅ Fetched {len(response.text)} chars, encoding={response.encoding}")
    return response.text


async def fetch_nbu_rates() -> List[Tuple[str, float, float]]:
    """
    Fetch NBU exchange rates.
    
    Returns:
        List of (currency_code, buy_rate, sell_rate) tuples
    """
    logger.info(f"🏦 Fetching NBU rates from {NBU_CONFIG['url']}")
    
    try:
        # Run sync request in executor to avoid blocking
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, fetch_html_sync)
        
        # Parse HTML
        rates = parse_nbu_html(html)
        logger.info(f"✅ Parsed {len(rates)} rates from NBU")
        
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching NBU rates: {e}", exc_info=True)
        return []


def parse_nbu_html(html: str) -> List[Tuple[str, float, float]]:
    """
    Parse NBU HTML to extract exchange rates.
    
    NBU stores rates in <option> elements with data-buy and data-sell attributes:
    <option value="USD" data-buy="12 080" data-sell="12 140">USD</option>
    
    Args:
        html: HTML content from NBU website
        
    Returns:
        List of (currency_code, buy_rate, sell_rate) tuples
    """
    rates = []
    seen_currencies = set()  # Track unique currencies to avoid duplicates
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all <option> elements with currency data
        options = soup.find_all('option', attrs={'data-buy': True, 'data-sell': True})
        logger.info(f"🔍 Found {len(options)} option elements with rate data")
        
        for option in options:
            try:
                code_raw = option.get('value')
                if not code_raw or not isinstance(code_raw, str):
                    continue
                code = code_raw.upper()
                if code not in SUPPORTED_CURRENCIES:
                    continue
                
                # Skip if we've already seen this currency
                if code in seen_currencies:
                    continue
                
                # Get buy/sell rates from data attributes
                buy_raw = option.get('data-buy', '')
                sell_raw = option.get('data-sell', '')
                buy_str = str(buy_raw).replace(' ', '').replace(',', '') if buy_raw else ''
                sell_str = str(sell_raw).replace(' ', '').replace(',', '') if sell_raw else ''
                
                # Skip if either is missing or "-"
                if not buy_str or not sell_str or buy_str == '-' or sell_str == '-':
                    logger.debug(f"Skipping {code}: incomplete rates (buy={buy_str}, sell={sell_str})")
                    continue
                
                try:
                    buy_rate = float(buy_str)
                    sell_rate = float(sell_str)
                    
                    if buy_rate > 0 and sell_rate > 0:
                        rates.append((code, buy_rate, sell_rate))
                        seen_currencies.add(code)
                        logger.debug(f"{code}: buy={buy_rate}, sell={sell_rate}")
                        
                except ValueError as e:
                    logger.debug(f"Failed to parse {code} rates: {e}")
                    continue
                    
            except Exception as e:
                logger.debug(f"Failed to parse option: {e}")
                continue
                    
    except Exception as e:
        logger.error(f"❌ Error parsing NBU HTML: {e}", exc_info=True)
    
    return rates


async def save_rates_to_db(rates: List[Tuple[str, float, float]]) -> None:
    """
    Save rates to database.
    
    Args:
        rates: List of (currency_code, buy_rate, sell_rate) tuples
    """
    if not rates:
        logger.warning("⚠️ No rates to save")
        return
    
    async with SessionLocal() as session:
        repo = BankRatesRepo(session)
        
        try:
            # Ensure bank exists
            bank = await repo.get_bank_by_slug(NBU_CONFIG["slug"])
            if not bank:
                bank = await repo.create_bank(
                    name=NBU_CONFIG["name"],
                    slug=NBU_CONFIG["slug"],
                    region="National",
                    website=NBU_CONFIG["website"]
                )
                logger.info(f"✅ Created bank: {bank.name}")
            
            # Save each rate
            saved_count = 0
            for currency_code, buy_rate, sell_rate in rates:
                try:
                    await repo.add_rate(
                        bank_id=bank.id,  # type: ignore
                        code=currency_code,
                        buy=buy_rate,
                        sell=sell_rate
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to save {currency_code} rate: {e}")
            
            await session.commit()
            logger.info(f"✅ Saved {saved_count}/{len(rates)} rates to database")
            
        except Exception as e:
            logger.error(f"❌ Database error: {e}", exc_info=True)
            await session.rollback()


async def collect():
    """Main collection function."""
    try:
        logger.info("Starting NBU collection...")
        
        # Fetch and parse rates
        rates = await fetch_nbu_rates()
        
        # Save to database
        if rates:
            await save_rates_to_db(rates)
            return len(rates)
        else:
            logger.warning("No rates collected")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Collection failed: {e}")
        return 0


if __name__ == "__main__":
    asyncio.run(collect())
