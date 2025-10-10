"""
Hamkorbank Exchange Rates Collector

Collects exchange rates from Hamkorbank API (JavaScript-loaded data).
Uses requests library for reliable HTTP handling.
"""

import asyncio
import logging
from typing import List, Tuple

import requests

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
    "api_url": "https://api-dbo.hamkorbank.uz/webflow/v1/exchanges",
    "website": "https://hamkorbank.uz"
}


def fetch_json_sync() -> dict:
    """Fetch Hamkorbank exchange rates from API."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://hamkorbank.uz/',
    }
    
    response = requests.get(HAMKORBANK_CONFIG["api_url"], headers=headers, timeout=20)
    response.raise_for_status()
    logger.info(f"✅ Fetched JSON response: {response.status_code}")
    return response.json()


async def fetch_hamkorbank_rates() -> List[Tuple[str, float, float]]:
    """Fetch Hamkorbank exchange rates from API."""
    logger.info(f"🏦 Fetching Hamkorbank rates from API")
    
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_json_sync)
        
        rates = parse_hamkorbank_json(data)
        logger.info(f"✅ Parsed {len(rates)} rates from Hamkorbank API")
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching Hamkorbank rates: {e}", exc_info=True)
        return []


def parse_hamkorbank_json(data: dict) -> List[Tuple[str, float, float]]:
    """Parse Hamkorbank JSON API response to extract exchange rates.
    
    Expected JSON structure:
    {
      "data": [
        {
          "code": "USD",
          "buy": 12700.0,
          "sell": 12800.0,
          ...
        }
      ]
    }
    """
    rates = []
    
    try:
        # Log the data structure for debugging
        logger.info(f"� JSON keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        
        # Handle different possible JSON structures
        exchanges = []
        if isinstance(data, dict):
            # Try common keys
            for key in ['data', 'rates', 'exchanges', 'result']:
                if key in data:
                    exchanges = data[key]
                    break
            # If no key matches, assume data itself is the list
            if not exchanges and 'code' in data:
                exchanges = [data]
        elif isinstance(data, list):
            exchanges = data
        
        logger.info(f"📊 Found {len(exchanges)} exchange entries")
        
        for item in exchanges:
            try:
                # Extract currency code
                code = item.get('code', '').upper()
                if not code:
                    # Try alternative keys
                    code = item.get('currency', '').upper()
                if not code:
                    code = item.get('currencyCode', '').upper()
                
                if code not in SUPPORTED_CURRENCIES:
                    continue
                
                # Extract buy and sell rates
                buy_rate = item.get('buy') or item.get('buyRate') or item.get('purchase')
                sell_rate = item.get('sell') or item.get('sellRate') or item.get('sale')
                
                if buy_rate and sell_rate:
                    buy_rate = float(buy_rate)
                    sell_rate = float(sell_rate)
                    
                    # Sanity check
                    if 0 < buy_rate < 1_000_000 and 0 < sell_rate < 1_000_000:
                        rates.append((code, buy_rate, sell_rate))
                        logger.info(f"💰 {code}: buy={buy_rate}, sell={sell_rate}")
                    else:
                        logger.warning(f"⚠️ Invalid rates for {code}: buy={buy_rate}, sell={sell_rate}")
                        
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Failed to parse exchange item: {e}")
                    
    except Exception as e:
        logger.error(f"❌ Error parsing Hamkorbank JSON: {e}", exc_info=True)
    
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
