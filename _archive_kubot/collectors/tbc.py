"""
TBC Bank Exchange Rates Collector

Collects exchange rates from TBC Bank.
Uses requests library for reliable HTTP handling.
"""

import asyncio
import logging
from typing import List, Tuple
import json

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

TBC_CONFIG = {
    "name": "TBC Bank",
    "slug": "tbc",
    "url": "https://tbcbank.uz/uz/currency/",
    "website": "https://tbcbank.uz"
}


def fetch_data_sync() -> tuple[str, dict | str]:
    """Fetch TBC Bank data - returns (content_type, data)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/html, */*',
    }
    
    response = requests.get(TBC_CONFIG["url"], headers=headers, timeout=20)
    response.raise_for_status()
    
    content_type = response.headers.get('content-type', '').lower()
    logger.info(f"✅ Fetched response, content-type={content_type}")
    
    if 'json' in content_type:
        try:
            return ('json', response.json())
        except:
            pass
    
    return ('html', response.text)


async def fetch_tbc_rates() -> List[Tuple[str, float, float]]:
    """Fetch TBC Bank exchange rates."""
    logger.info(f"🏦 Fetching TBC rates from {TBC_CONFIG['url']}")
    
    try:
        loop = asyncio.get_event_loop()
        content_type, data = await loop.run_in_executor(None, fetch_data_sync)
        
        if content_type == 'json' and isinstance(data, dict):
            rates = parse_tbc_json(data)
        elif isinstance(data, str):
            rates = parse_tbc_html(data)
        else:
            logger.error(f"❌ Unexpected data type: {type(data)}")
            return []
            
        logger.info(f"✅ Parsed {len(rates)} rates from TBC")
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching TBC rates: {e}", exc_info=True)
        return []


def parse_tbc_json(data: dict) -> List[Tuple[str, float, float]]:
    """Parse TBC Bank JSON to extract exchange rates."""
    rates = []
    
    try:
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('data', data.get('rates', [data]))
        else:
            items = [data]
        
        for item in items:
            try:
                code = None
                for key in ['code', 'currency', 'ccy']:
                    if key in item:
                        code = str(item[key]).upper()
                        break
                
                if not code or code not in SUPPORTED_CURRENCIES:
                    continue
                
                buy = sell = None
                for buy_key in ['buy', 'buying', 'buyRate']:
                    if buy_key in item:
                        buy = float(item[buy_key])
                        break
                        
                for sell_key in ['sell', 'selling', 'sellRate']:
                    if sell_key in item:
                        sell = float(item[sell_key])
                        break
                
                if buy is None and sell is None:
                    for rate_key in ['rate', 'value']:
                        if rate_key in item:
                            rate = float(item[rate_key])
                            buy = sell = rate
                            break
                
                if buy and sell and buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
                    logger.debug(f"{code}: buy={buy}, sell={sell}")
                    
            except Exception as e:
                logger.debug(f"Failed to parse JSON item: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Error parsing TBC JSON: {e}", exc_info=True)
    
    return rates


def parse_tbc_html(html: str) -> List[Tuple[str, float, float]]:
    """Parse TBC Bank HTML to extract exchange rates."""
    rates = []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # TBC website uses div-based structure, not tables
        items = soup.find_all('div', class_='body-item')
        logger.info(f"🔍 Found {len(items)} rate containers")
        
        for item in items:
            try:
                wrapper = item.find('div', class_='body-item-wrapper')
                if not wrapper:
                    continue
                
                # Extract currency code from flag div
                currency_div = wrapper.find('div', class_='flag btn-text-1')
                if not currency_div:
                    continue
                
                code = currency_div.get_text(strip=True).upper()
                if code not in SUPPORTED_CURRENCIES:
                    continue
                
                # Extract rate from rate div
                rate_div = wrapper.find('div', class_='rate paragraph-4')
                if not rate_div:
                    continue
                
                # Parse rate value - handle format like "16,229.57 ↗"
                rate_text = rate_div.get_text(strip=True)
                
                # First split by whitespace to remove arrows/icons
                parts = rate_text.split()
                if parts:
                    rate_text = parts[0]
                
                # Remove commas (used as thousands separators)
                rate_text = rate_text.replace(',', '')
                
                # Remove any remaining whitespace
                rate_text = rate_text.strip()
                
                try:
                    rate = float(rate_text)
                    # TBC shows single rate (appears to be mid-market rate)
                    rates.append((code, rate, rate))
                    logger.debug(f"💰 {code}: {rate}")
                except ValueError as e:
                    logger.debug(f"Failed to parse rate '{rate_text}' for {code}: {e}")
                    continue
                        
            except Exception as e:
                logger.debug(f"Failed to parse item: {e}")
                continue
                    
    except Exception as e:
        logger.error(f"❌ Error parsing TBC HTML: {e}", exc_info=True)
    
    return rates


async def save_rates_to_db(rates: List[Tuple[str, float, float]]) -> None:
    """Save rates to database."""
    if not rates:
        logger.warning("⚠️ No rates to save")
        return
    
    async with SessionLocal() as session:
        repo = BankRatesRepo(session)
        
        try:
            bank = await repo.get_bank_by_slug(TBC_CONFIG["slug"])
            if not bank:
                bank = await repo.create_bank(
                    name=TBC_CONFIG["name"],
                    slug=TBC_CONFIG["slug"],
                    region="Commercial",
                    website=TBC_CONFIG["website"]
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
        logger.info("Starting TBC collection...")
        rates = await fetch_tbc_rates()
        
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
