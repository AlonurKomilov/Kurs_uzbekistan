"""
Hamkorbank Exchange Rates Collector

Collects exchange rates from Hamkorbank using HTML scraping.
Uses requests library for reliable HTTP handling.
"""

import asyncio
import logging
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

from core.repos import BankRatesRepo
from infrastructure.db import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "GBP", "JPY", "CHF", "KRW", "CNY"]

HAMKORBANK_CONFIG = {
    "name": "Hamkorbank",
    "slug": "hamkorbank",
    "url": "https://hamkorbank.uz/exchange-rate/",
    "website": "https://hamkorbank.uz"
}


def fetch_html_sync() -> str:
    """Fetch Hamkorbank HTML page."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    response = requests.get(HAMKORBANK_CONFIG["url"], headers=headers, timeout=20)
    response.raise_for_status()
    logger.info(f"✅ Fetched {len(response.text)} chars")
    return response.text


async def fetch_hamkorbank_rates() -> List[Tuple[str, float, float]]:
    """Fetch Hamkorbank exchange rates."""
    logger.info(f"🏦 Fetching Hamkorbank rates from {HAMKORBANK_CONFIG['url']}")
    
    try:
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, fetch_html_sync)
        
        rates = parse_hamkorbank_html(html)
        logger.info(f"✅ Parsed {len(rates)} rates from Hamkorbank")
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching Hamkorbank rates: {e}", exc_info=True)
        return []


def parse_hamkorbank_html(html: str) -> List[Tuple[str, float, float]]:
    """Parse Hamkorbank HTML to extract exchange rates."""
    rates = []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for tables with exchange rates
        tables = soup.find_all('table')
        logger.info(f"🔍 Found {len(tables)} tables")
        
        # Also look for divs that might contain rates
        rate_containers = soup.find_all(['div', 'tr', 'li'], class_=lambda x: x and ('rate' in x.lower() or 'currency' in x.lower() or 'exchange' in x.lower()))
        logger.info(f"🔍 Found {len(rate_containers)} potential rate containers")
        
        # Search in tables first
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                try:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) < 2:
                        continue
                    
                    # Look for currency code
                    code = None
                    for col in cols:
                        text = col.get_text(strip=True).upper()
                        if text in SUPPORTED_CURRENCIES:
                            code = text
                            break
                    
                    if not code:
                        continue
                    
                    # Extract numeric values
                    values = []
                    for col in cols:
                        try:
                            text = col.get_text(strip=True).replace(',', '').replace(' ', '')
                            val = float(text)
                            if val > 0:
                                values.append(val)
                        except ValueError:
                            continue
                    
                    if len(values) >= 2:
                        # Assume first value is buy, second is sell
                        rates.append((code, values[0], values[1]))
                        logger.debug(f"{code}: buy={values[0]}, sell={values[1]}")
                    elif len(values) == 1:
                        # Single rate - use for both
                        rates.append((code, values[0], values[0]))
                        logger.debug(f"{code}: {values[0]}")
                        
                except Exception as e:
                    logger.debug(f"Failed to parse row: {e}")
                    continue
        
        # If no rates found in tables, try other containers
        if not rates:
            for container in rate_containers:
                try:
                    text = container.get_text(strip=True).upper()
                    for currency in SUPPORTED_CURRENCIES:
                        if currency in text:
                            # Extract numbers near currency code
                            import re
                            numbers = re.findall(r'\d+[\.,]?\d*', text)
                            if numbers:
                                values = [float(n.replace(',', '.')) for n in numbers if float(n.replace(',', '.')) > 0]
                                if len(values) >= 2:
                                    rates.append((currency, values[0], values[1]))
                                    logger.debug(f"{currency}: buy={values[0]}, sell={values[1]}")
                                    break
                                elif len(values) == 1:
                                    rates.append((currency, values[0], values[0]))
                                    logger.debug(f"{currency}: {values[0]}")
                                    break
                except Exception as e:
                    continue
                    
    except Exception as e:
        logger.error(f"❌ Error parsing Hamkorbank HTML: {e}", exc_info=True)
    
    return rates


async def save_rates_to_db(rates: List[Tuple[str, float, float]]) -> None:
    """Save rates to database."""
    if not rates:
        logger.warning("⚠️ No rates to save")
        return
    
    async with SessionLocal() as session:
        repo = BankRatesRepo(session)
        
        try:
            bank = await repo.get_bank_by_slug(HAMKORBANK_CONFIG["slug"])
            if not bank:
                bank = await repo.create_bank(
                    name=HAMKORBANK_CONFIG["name"],
                    slug=HAMKORBANK_CONFIG["slug"],
                    region="Commercial",
                    website=HAMKORBANK_CONFIG["website"]
                )
                logger.info(f"✅ Created bank: {bank.name}")
            
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
        logger.info("Starting Hamkorbank collection...")
        rates = await fetch_hamkorbank_rates()
        
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
