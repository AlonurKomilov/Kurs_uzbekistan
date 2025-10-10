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


def fetch_html_sync() -> str:
    """Fetch Ipoteka Bank HTML page using requests library (sync)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    response = requests.get(IPOTEKA_CONFIG["url"], headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    logger.info(f"✅ Fetched {len(response.text)} chars, status={response.status_code}")
    
    return response.text


async def fetch_ipoteka_rates() -> List[Tuple[str, float, float]]:
    """Fetch Ipoteka Bank exchange rates."""
    logger.info(f"🏦 Fetching Ipoteka rates from {IPOTEKA_CONFIG['url']}")
    
    try:
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, fetch_html_sync)
        
        rates = parse_ipoteka_html(html)
        logger.info(f"✅ Parsed {len(rates)} rates from Ipoteka")
        return rates
            
    except Exception as e:
        logger.error(f"❌ Error fetching Ipoteka rates: {e}", exc_info=True)
        return []


def parse_ipoteka_html(html: str) -> List[Tuple[str, float, float]]:
    """
    Parse Ipoteka Bank HTML to extract exchange rates.
    
    Structure:
    <td><b>USD</b></td>
    <td>...<span>12 065</span>...</td>  <!-- buy rate -->
    <td>...<span>12 200</span>...</td>  <!-- sell rate -->
    
    Args:
        html: HTML content from Ipoteka website
        
    Returns:
        List of (currency_code, buy_rate, sell_rate) tuples
    """
    rates = []
    seen_currencies = set()
    
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all <b> tags (currency codes)
        currency_tags = soup.find_all('b')
        logger.info(f"🔍 Found {len(currency_tags)} <b> tags")
        
        for tag in currency_tags:
            try:
                code = tag.get_text(strip=True).upper()
                if not code or code not in SUPPORTED_CURRENCIES or code in seen_currencies:
                    continue
                
                # Find parent <td> and then siblings
                td = tag.find_parent('td')
                if not td:
                    continue
                
                # Get next two <td> siblings for buy and sell rates
                next_tds = []
                sibling = td.find_next_sibling('td')
                while sibling and len(next_tds) < 2:
                    next_tds.append(sibling)
                    sibling = sibling.find_next_sibling('td')
                
                if len(next_tds) < 2:
                    logger.debug(f"Not enough sibling <td> for {code}")
                    continue
                
                # Extract rates from spans
                buy_span = next_tds[0].find('span')
                sell_span = next_tds[1].find('span')
                
                if not buy_span or not sell_span:
                    logger.debug(f"Missing spans for {code}")
                    continue
                
                buy_str = buy_span.get_text(strip=True).replace(' ', '').replace(',', '')
                sell_str = sell_span.get_text(strip=True).replace(' ', '').replace(',', '')
                
                try:
                    buy_rate = float(buy_str)
                    sell_rate = float(sell_str)
                    
                    if buy_rate > 0 and sell_rate > 0:
                        rates.append((code, buy_rate, sell_rate))
                        seen_currencies.add(code)
                        logger.debug(f"{code}: buy={buy_rate}, sell={sell_rate}")
                        
                except ValueError as e:
                    logger.debug(f"Failed to parse {code} rates: buy={buy_str}, sell={sell_str}, error={e}")
                    continue
                    
            except Exception as e:
                logger.debug(f"Failed to parse currency tag: {e}")
                continue
                    
    except Exception as e:
        logger.error(f"❌ Error parsing Ipoteka HTML: {e}", exc_info=True)
    
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
