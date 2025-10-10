"""
Ipoteka Bank Exchange Rates Collector

Collects exchange rates from Ipoteka Bank using JSON API.
Uses requests library for reliable HTTP handling.
"""

import asyncio
import logging
from typing import List, Tuple
import json

import requests
import urllib3

from core.repos import BankRatesRepo
from infrastructure.db import SessionLocal

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB", "GBP", "JPY", "CHF", "KRW", "CNY"]

IPOTEKA_CONFIG = {
    "name": "Ipoteka Bank",
    "slug": "ipoteka",
    "url": "https://www.ipotekabank.uz/currency/",
    "website": "https://www.ipotekabank.uz"
}


def fetch_json_sync() -> dict:
    """Fetch Ipoteka Bank JSON data using requests library (sync)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
    }
    
    response = requests.get(IPOTEKA_CONFIG["url"], headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    logger.info(f"✅ Fetched response, status={response.status_code}")
    
    return response.json()


async def fetch_ipoteka_rates() -> List[Tuple[str, float, float]]:
    """Fetch Ipoteka Bank exchange rates."""
    logger.info(f"🏦 Fetching Ipoteka rates from {IPOTEKA_CONFIG['url']}")
    
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_json_sync)
        
        rates = parse_ipoteka_json(data)
        logger.info(f"✅ Parsed {len(rates)} rates from Ipoteka")
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching Ipoteka rates: {e}", exc_info=True)
        return []


def parse_ipoteka_json(data: dict) -> List[Tuple[str, float, float]]:
    """Parse Ipoteka Bank JSON to extract exchange rates."""
    rates = []
    
    try:
        # Try common JSON structures
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and 'data' in data:
            items = data['data'] if isinstance(data['data'], list) else [data['data']]
        elif isinstance(data, dict) and 'rates' in data:
            items = data['rates'] if isinstance(data['rates'], list) else [data['rates']]
        else:
            items = [data]
        
        for item in items:
            try:
                # Look for currency code
                code = None
                for key in ['code', 'currency', 'ccy', 'Code', 'Currency']:
                    if key in item:
                        code = str(item[key]).upper()
                        break
                
                if not code or code not in SUPPORTED_CURRENCIES:
                    continue
                
                # Look for buy/sell rates
                buy = sell = None
                for buy_key in ['buy', 'buying', 'buy_rate', 'buyRate']:
                    if buy_key in item:
                        buy = float(item[buy_key])
                        break
                        
                for sell_key in ['sell', 'selling', 'sell_rate', 'sellRate']:
                    if sell_key in item:
                        sell = float(item[sell_key])
                        break
                
                # If no buy/sell, look for single rate
                if buy is None and sell is None:
                    for rate_key in ['rate', 'value', 'price']:
                        if rate_key in item:
                            rate = float(item[rate_key])
                            buy = sell = rate
                            break
                
                if buy and sell and buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
                    logger.debug(f"{code}: buy={buy}, sell={sell}")
                    
            except Exception as e:
                logger.debug(f"Failed to parse item: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Error parsing Ipoteka JSON: {e}", exc_info=True)
    
    return rates


async def save_rates_to_db(rates: List[Tuple[str, float, float]]) -> None:
    """Save rates to database."""
    if not rates:
        logger.warning("⚠️ No rates to save")
        return
    
    async with SessionLocal() as session:
        repo = BankRatesRepo(session)
        
        try:
            bank = await repo.get_bank_by_slug(IPOTEKA_CONFIG["slug"])
            if not bank:
                bank = await repo.create_bank(
                    name=IPOTEKA_CONFIG["name"],
                    slug=IPOTEKA_CONFIG["slug"],
                    region="Commercial",
                    website=IPOTEKA_CONFIG["website"]
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
        logger.info("Starting Ipoteka collection...")
        rates = await fetch_ipoteka_rates()
        
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
