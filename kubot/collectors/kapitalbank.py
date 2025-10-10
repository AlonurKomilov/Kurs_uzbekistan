"""
Kapitalbank Exchange Rates Collector

Collects exchange rates from Kapitalbank using HTML scraping.
Uses requests library for reliable HTTP handling (httpx has Brotli decompression bug).
"""

import asyncio
import logging
from typing import List, Tuple
from datetime import datetime

import requests
import urllib3
from bs4 import BeautifulSoup

from core.repos import BankRatesRepo
from infrastructure.db import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable SSL warnings (Kapitalbank may have cert issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "GBP", "JPY", "CHF", "KRW", "CNY"]

KAPITALBANK_CONFIG = {
    "name": "Kapitalbank",
    "slug": "kapitalbank",
    "url": "https://kapitalbank.uz/en/services/exchange-rates/",
    "website": "https://kapitalbank.uz"
}


def fetch_html_sync() -> str:
    """Fetch Kapitalbank HTML page using requests library (sync)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    response = requests.get(KAPITALBANK_CONFIG["url"], headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    logger.info(f"✅ Fetched {len(response.text)} chars, encoding={response.encoding}")
    return response.text


async def fetch_kapitalbank_rates() -> List[Tuple[str, float, float]]:
    """
    Fetch Kapitalbank exchange rates using requests library.
    
    Returns:
        List of (currency_code, buy_rate, sell_rate) tuples
    """
    logger.info(f"🏦 Fetching Kapitalbank rates from {KAPITALBANK_CONFIG['url']}")
    
    try:
        # Run sync request in executor to avoid blocking
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, fetch_html_sync)
        
        # Parse HTML
        rates = parse_kapitalbank_html(html)
        logger.info(f"✅ Parsed {len(rates)} rates from Kapitalbank")
        
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching Kapitalbank rates: {e}", exc_info=True)
        return []


def parse_kapitalbank_html(html: str) -> List[Tuple[str, float, float]]:
    """
    Parse Kapitalbank HTML to extract exchange rates.
    
    Args:
        html: HTML content from Kapitalbank website
        
    Returns:
        List of (currency_code, buy_rate, sell_rate) tuples
    """
    rates = []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all rate boxes
        rate_boxes = soup.find_all('div', class_='kapitalbank_currency_tablo_rate_box')
        logger.info(f"🔍 Found {len(rate_boxes)} rate boxes")
        
        if len(rate_boxes) == 0:
            logger.warning(f"⚠️ No rate boxes found, checking alternative structures...")
            
            # Try to find currency codes in the HTML
            all_text = soup.get_text()
            for currency in SUPPORTED_CURRENCIES:
                if currency in all_text:
                    logger.info(f"✅ Found '{currency}' in HTML text")
                else:
                    logger.warning(f"❌ '{currency}' not found in HTML text")
        
        for box in rate_boxes:
            try:
                # Find currency code
                code_div = box.find('div', class_='kapitalbank_currency_tablo_type_box')
                if not code_div:
                    continue
                    
                code = code_div.text.strip().upper()
                if code not in SUPPORTED_CURRENCIES:
                    continue
                
                # Find buy rate
                buy_div = box.find('div', class_='kapitalbank_currency_tablo_type_value')
                if not buy_div:
                    continue
                buy_rate = float(buy_div.text.strip().replace(' ', '').replace(',', '.'))
                
                # Find sell rate (next sibling)
                sell_div = buy_div.find_next_sibling('div', class_='kapitalbank_currency_tablo_type_value')
                if not sell_div:
                    continue
                sell_rate = float(sell_div.text.strip().replace(' ', '').replace(',', '.'))
                
                rates.append((code, buy_rate, sell_rate))
                logger.info(f"💰 {code}: buy={buy_rate}, sell={sell_rate}")
                
            except Exception as e:
                logger.error(f"Error parsing rate box: {e}")
                continue
        
    except Exception as e:
        logger.error(f"❌ Error parsing Kapitalbank HTML: {e}", exc_info=True)
    
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
            bank = await repo.get_bank_by_slug(KAPITALBANK_CONFIG["slug"])
            if not bank:
                bank = await repo.create_bank(
                    name=KAPITALBANK_CONFIG["name"],
                    slug=KAPITALBANK_CONFIG["slug"],
                    region="National",
                    website=KAPITALBANK_CONFIG["website"]
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
        logger.info("Starting Kapitalbank collection...")
        
        # Fetch and parse rates
        rates = await fetch_kapitalbank_rates()
        
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
