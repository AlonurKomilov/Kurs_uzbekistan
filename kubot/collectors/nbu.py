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
    
    Args:
        html: HTML content from NBU website
        
    Returns:
        List of (currency_code, buy_rate, sell_rate) tuples
    """
    rates = []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # NBU usually shows rates in a table
        # Look for table with exchange rates
        tables = soup.find_all('table')
        logger.info(f"🔍 Found {len(tables)} tables")
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                try:
                    cols = row.find_all('td')
                    if len(cols) < 3:
                        continue
                    
                    # Try to find currency code (usually in first column)
                    for col in cols:
                        text = col.get_text(strip=True).upper()
                        if text in SUPPORTED_CURRENCIES:
                            code = text
                            break
                    else:
                        continue
                    
                    # Look for numeric values (exchange rates)
                    numeric_values = []
                    for col in cols:
                        try:
                            text = col.get_text(strip=True).replace(',', '').replace(' ', '')
                            value = float(text)
                            if value > 0:
                                numeric_values.append(value)
                        except ValueError:
                            continue
                    
                    # Typically we expect at least one rate value
                    if numeric_values:
                        # If only one rate, use it for both buy and sell
                        rate = numeric_values[0]
                        rates.append((code, rate, rate))
                        logger.debug(f"{code}: {rate}")
                        
                except Exception as e:
                    logger.debug(f"Failed to parse row: {e}")
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
