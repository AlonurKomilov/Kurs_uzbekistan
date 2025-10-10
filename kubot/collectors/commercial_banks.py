"""
Commercial Banks Exchange Rates Collector for Uzbekistan

This collector fetches exchange rates from major commercial banks in Uzbekistan
to provide better rate information beyond just the Central Bank rates.

Supported Banks:
- NBU (National Bank of Uzbekistan)
- Ipoteka Bank
- Hamkorbank
- Kapitalbank
- Qishloq Qurilish Bank
- TBC Bank
- Turonbank
- Universal Bank
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import requests
import urllib3
from typing import List, Dict, Optional, Tuple
import httpx
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from bs4 import BeautifulSoup
import re

# Disable SSL warnings for requests library
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.repos import BankRatesRepo
from infrastructure.db import SessionLocal

logger = logging.getLogger(__name__)

# Supported currency codes we want to track (matching CBU collector)
SUPPORTED_CURRENCIES = {"USD", "EUR", "RUB", "GBP", "JPY", "CHF", "KRW", "CNY"}

# Bank configurations with their API endpoints and parsing methods
BANK_CONFIGS = {
    "nbu": {
        "name": "National Bank of Uzbekistan",
        "slug": "nbu",
        "url": "https://nbu.uz/en/for-individuals-exchange-rates/",
        "method": "api_json",
        "website": "https://nbu.uz"
    },
    "ipoteka": {
        "name": "Ipoteka Bank",
        "slug": "ipoteka",
        "url": "https://www.ipotekabank.uz/currency/",
        "method": "api_json", 
        "website": "https://www.ipotekabank.uz"
    },
    "hamkorbank": {
        "name": "Hamkorbank",
        "slug": "hamkorbank",
        "url": "https://hamkorbank.uz/exchange-rate/",
        "method": "html_scraping",
        "website": "https://www.hamkorbank.uz"
    },
    "kapitalbank": {
        "name": "Kapitalbank",
        "slug": "kapitalbank", 
        "url": "https://kapitalbank.uz/uz/services/exchange-rates/",
        "method": "html_scraping",
        "website": "https://kapitalbank.uz"
    },
    "qishloq": {
        "name": "Qishloq Qurilish Bank",
        "slug": "qishloq",
        "url": "https://www.qqb.uz/",
        "method": "html_scraping",
        "website": "https://www.qqb.uz"
    },
    "tbc": {
        "name": "TBC Bank Uzbekistan",
        "slug": "tbc", 
        "url": "https://tbcbank.uz/",
        "method": "api_json",
        "website": "https://tbcbank.uz"
    },
    "turonbank": {
        "name": "Turonbank",
        "slug": "turonbank",
        "url": "https://turonbank.uz/",
        "method": "html_scraping", 
        "website": "https://turonbank.uz"
    },
    "universal": {
        "name": "Universal Bank",
        "slug": "universal",
        "url": "https://universalbank.uz/",
        "method": "api_json",
        "website": "https://universalbank.uz"
    }
}


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True
)
def _fetch_kapitalbank_sync(url: str) -> str:
    """
    Fetch Kapitalbank HTML using requests library (sync).
    httpx has issues with Brotli decompression, so we use requests instead.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    response = requests.get(url, headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    logger.info(f"Kapitalbank: Fetched {len(response.text)} chars, encoding={response.encoding}")
    return response.text


async def _fetch_bank_data(bank_slug: str, url: str, method: str) -> Optional[Dict]:
    """Fetch bank rates data with retry mechanism."""
    logger.info(f"Fetching {bank_slug} rates from {url}")
    
    # Special handling for Kapitalbank - use requests instead of httpx
    if bank_slug == "kapitalbank" and method == "html_scraping":
        try:
            # Run sync requests in executor to avoid blocking
            loop = asyncio.get_event_loop()
            html = await loop.run_in_executor(None, _fetch_kapitalbank_sync, url)
            return {"type": "html", "data": html}
        except Exception as e:
            logger.error(f"Failed to fetch data from {bank_slug}: {e}")
            raise
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/html, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        async with httpx.AsyncClient(
            timeout=20.0, 
            headers=headers,
            follow_redirects=True,  # Enable automatic redirect following
            verify=False  # Disable SSL verification for banks with cert issues
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            if method == "api_json":
                data = response.json()
                logger.debug(f"Successfully fetched JSON data from {bank_slug}: {len(data) if isinstance(data, list) else 'object'}")
                return {"type": "json", "data": data}
            elif method == "html_scraping":
                html = response.text
                logger.debug(f"Successfully fetched HTML from {bank_slug}: {len(html)} chars")
                return {"type": "html", "data": html}
            
    except Exception as e:
        logger.error(f"Failed to fetch data from {bank_slug}: {e}")
        raise


def _parse_nbu_rates(data: Dict) -> List[Tuple[str, float, float]]:
    """Parse NBU bank rates from JSON response."""
    rates = []
    try:
        json_data = data.get("data", [])
        for item in json_data:
            code = item.get("code", "").upper()
            if code in SUPPORTED_CURRENCIES:
                buy = float(item.get("buy", 0))
                sell = float(item.get("sell", 0))
                if buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
                    logger.debug(f"NBU {code}: buy={buy}, sell={sell}")
    except Exception as e:
        logger.error(f"Error parsing NBU rates: {e}")
    return rates


def _parse_ipoteka_rates(data: Dict) -> List[Tuple[str, float, float]]:
    """Parse Ipoteka Bank rates from JSON response."""
    rates = []
    try:
        json_data = data.get("data", [])
        for item in json_data:
            code = item.get("currency", "").upper() 
            if code in SUPPORTED_CURRENCIES:
                buy = float(item.get("buy_rate", 0))
                sell = float(item.get("sell_rate", 0))
                if buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
                    logger.debug(f"Ipoteka {code}: buy={buy}, sell={sell}")
    except Exception as e:
        logger.error(f"Error parsing Ipoteka rates: {e}")
    return rates


def _parse_kapitalbank_rates(html: str) -> List[Tuple[str, float, float]]:
    """Parse Kapitalbank rates from HTML scraping."""
    rates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Kapitalbank uses specific div structure for rates
        # Structure: <div class="kapitalbank_currency_tablo_rate_box">
        #              <div class="kapitalbank_currency_tablo_type_box">USD</div>
        #              <div class="kapitalbank_currency_tablo_type_value">12135</div>
        #            </div>
        
        # Find all rate containers
        rate_boxes = soup.find_all('div', class_='kapitalbank_currency_tablo_rate_box')
        logger.info(f"Kapitalbank: Found {len(rate_boxes)} rate boxes")
        
        for box in rate_boxes:
            try:
                # Find currency code
                code_div = box.find('div', class_='kapitalbank_currency_tablo_type_box')
                if not code_div:
                    continue
                    
                code = code_div.get_text(strip=True).upper()
                
                # Only process supported currencies
                if code not in SUPPORTED_CURRENCIES:
                    continue
                
                # Find the rate value
                value_div = box.find('div', class_='kapitalbank_currency_tablo_type_value')
                if not value_div:
                    continue
                
                # Extract number (remove commas and spaces)
                rate_text = value_div.get_text(strip=True).replace(',', '').replace(' ', '')
                rate = float(rate_text)
                
                # Kapitalbank shows selling rate (bank sells to customer)
                # Use same value for buy/sell since we only have one value
                if rate > 100 and rate < 100000:
                    rates.append((code, rate, rate))
                    logger.info(f"Kapitalbank {code}: Successfully parsed rate={rate}")
                else:
                    logger.warning(f"Kapitalbank {code}: Rate {rate} out of range (100-100000)")
                    
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parsing Kapitalbank rate box: {e}")
                continue
        
        # If no rates found with primary method, try fallback to tables
        if not rates:
            logger.warning(f"Kapitalbank: Primary parsing failed (found {len(rate_boxes)} boxes but 0 rates), trying table fallback")
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        text = ' '.join([cell.get_text(strip=True) for cell in cells])
                        
                        for code in SUPPORTED_CURRENCIES:
                            if code in text.upper():
                                try:
                                    # Extract numbers from cells
                                    numbers = []
                                    for cell in cells:
                                        cell_text = cell.get_text(strip=True)
                                        # Remove non-numeric characters except dot
                                        num_text = re.sub(r'[^\d.]', '', cell_text.replace(',', ''))
                                        if num_text and len(num_text) >= 4:
                                            numbers.append(float(num_text))
                                    
                                    if numbers:
                                        rate = numbers[0]
                                        if rate > 100 and rate < 100000:
                                            rates.append((code, rate, rate))
                                            logger.debug(f"Kapitalbank {code} (table): rate={rate}")
                                            break
                                except (ValueError, IndexError):
                                    continue
                            
    except Exception as e:
        logger.error(f"Error parsing Kapitalbank HTML: {e}")
    return rates


def _parse_tbc_rates(data: Dict) -> List[Tuple[str, float, float]]:
    """Parse TBC Bank rates from JSON response."""
    rates = []
    try:
        json_data = data.get("data", [])
        for item in json_data:
            code = item.get("currency_code", "").upper()
            if code in SUPPORTED_CURRENCIES:
                buy = float(item.get("buy_rate", 0))
                sell = float(item.get("sell_rate", 0))
                if buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
                    logger.debug(f"TBC {code}: buy={buy}, sell={sell}")
    except Exception as e:
        logger.error(f"Error parsing TBC rates: {e}")
    return rates


def _parse_universal_rates(data: Dict) -> List[Tuple[str, float, float]]:
    """Parse Universal Bank rates from JSON response."""
    rates = []
    try:
        json_data = data.get("data", {})
        exchange_rates = json_data.get("exchange_rates", [])
        for item in exchange_rates:
            code = item.get("currency", "").upper()
            if code in SUPPORTED_CURRENCIES:
                buy = float(item.get("buy", 0))
                sell = float(item.get("sell", 0))
                if buy > 0 and sell > 0:
                    rates.append((code, buy, sell))
                    logger.debug(f"Universal {code}: buy={buy}, sell={sell}")
    except Exception as e:
        logger.error(f"Error parsing Universal rates: {e}")
    return rates


def _parse_hamkorbank_html(html: str) -> List[Tuple[str, float, float]]:
    """Parse Hamkorbank rates from HTML scraping."""
    rates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for currency table
        currency_tables = soup.find_all('table', class_=re.compile(r'currency|exchange|rate'))
        if not currency_tables:
            # Fallback: look for any table containing currency data
            currency_tables = soup.find_all('table')
        
        for table in currency_tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # Extract currency code, buy rate, sell rate
                    code_text = cells[0].get_text(strip=True).upper()
                    
                    # Extract 3-letter currency code
                    code_match = re.search(r'\b(USD|EUR|RUB)\b', code_text)
                    if code_match:
                        code = code_match.group(1)
                        try:
                            buy = float(re.sub(r'[^\d.]', '', cells[1].get_text(strip=True)))
                            sell = float(re.sub(r'[^\d.]', '', cells[2].get_text(strip=True)))
                            if buy > 0 and sell > 0:
                                rates.append((code, buy, sell))
                                logger.debug(f"Hamkorbank {code}: buy={buy}, sell={sell}")
                        except (ValueError, IndexError):
                            continue
                            
    except Exception as e:
        logger.error(f"Error parsing Hamkorbank HTML: {e}")
    return rates


def _parse_qishloq_html(html: str) -> List[Tuple[str, float, float]]:
    """Parse Qishloq Qurilish Bank rates from HTML scraping."""
    rates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for exchange rates section
        rate_sections = soup.find_all(['div', 'section'], attrs={'class': re.compile(r'exchange|currency|rate')})  # type: ignore[arg-type]
        
        for section in rate_sections:
            # Look for currency data patterns
            currency_items = section.find_all(['div', 'span', 'td'], string=re.compile(r'USD|EUR|RUB'))  # type: ignore[arg-type]
            
            for item in currency_items:
                parent = item.parent
                if parent:
                    text = parent.get_text()
                    # Look for patterns like "USD 12750 12850"
                    match = re.search(r'(USD|EUR|RUB)\s+(\d+\.?\d*)\s+(\d+\.?\d*)', text)
                    if match:
                        code, buy, sell = match.groups()
                        try:
                            buy_rate = float(buy)
                            sell_rate = float(sell)
                            if buy_rate > 0 and sell_rate > 0:
                                rates.append((code, buy_rate, sell_rate))
                                logger.debug(f"Qishloq {code}: buy={buy_rate}, sell={sell_rate}")
                        except ValueError:
                            continue
                            
    except Exception as e:
        logger.error(f"Error parsing Qishloq HTML: {e}")
    return rates


def _parse_turonbank_html(html: str) -> List[Tuple[str, float, float]]:
    """Parse Turonbank rates from HTML scraping."""
    rates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for currency table or rate display
        rate_containers = soup.find_all(['table', 'div'], class_=re.compile(r'currency|exchange|rate'))
        
        for container in rate_containers:
            rows = container.find_all(['tr', 'div'])
            for row in rows:
                text = row.get_text()
                # Look for patterns with currency codes and rates
                for currency in SUPPORTED_CURRENCIES:
                    pattern = fr'{currency}\s*.*?(\d+\.?\d*)\s*.*?(\d+\.?\d*)'
                    match = re.search(pattern, text)
                    if match:
                        try:
                            buy_rate = float(match.group(1))
                            sell_rate = float(match.group(2))
                            if buy_rate > 0 and sell_rate > 0:
                                rates.append((currency, buy_rate, sell_rate))
                                logger.debug(f"Turonbank {currency}: buy={buy_rate}, sell={sell_rate}")
                        except ValueError:
                            continue
                            
    except Exception as e:
        logger.error(f"Error parsing Turonbank HTML: {e}")
    return rates


def _parse_bank_rates(bank_slug: str, response_data: Dict) -> List[Tuple[str, float, float]]:
    """Parse bank rates based on bank type and response format."""
    if response_data.get("type") == "json":
        data = response_data.get("data", {})
        
        if bank_slug == "nbu":
            return _parse_nbu_rates(data)
        elif bank_slug == "ipoteka":
            return _parse_ipoteka_rates(data)
        elif bank_slug == "tbc":
            return _parse_tbc_rates(data)
        elif bank_slug == "universal":
            return _parse_universal_rates(data)
            
    elif response_data.get("type") == "html":
        html = response_data.get("data", "")
        
        if bank_slug == "hamkorbank":
            return _parse_hamkorbank_html(html)
        elif bank_slug == "kapitalbank":
            return _parse_kapitalbank_rates(html)
        elif bank_slug == "qishloq":
            return _parse_qishloq_html(html)
        elif bank_slug == "turonbank":
            return _parse_turonbank_html(html)
    
    return []


async def _ensure_bank_exists(repo: BankRatesRepo, bank_config: Dict) -> int:
    """Ensure bank exists in database and return bank_id."""
    bank = await repo.get_bank_by_slug(bank_config["slug"])
    if not bank:
        bank = await repo.create_bank(
            name=bank_config["name"],
            slug=bank_config["slug"],
            region="Uzbekistan",
            website=bank_config["website"]
        )
        logger.info(f"Created new bank: {bank.name} (ID: {bank.id})")
    # Type checker doesn't understand SQLAlchemy attributes, but at runtime bank.id is an int
    return bank.id  # type: ignore


async def collect_bank_rates(bank_slug: str) -> Dict:
    """Collect rates for a specific bank."""
    logger.info(f"Starting collection for {bank_slug}")
    
    if bank_slug not in BANK_CONFIGS:
        raise ValueError(f"Unknown bank: {bank_slug}")
    
    config = BANK_CONFIGS[bank_slug]
    result = {
        "bank": bank_slug,
        "success": False,
        "rates_collected": 0,
        "errors": []
    }
    
    try:
        # Fetch data from bank
        response_data = await _fetch_bank_data(bank_slug, config["url"], config["method"])
        if not response_data:
            result["errors"].append("No data received")
            return result
        
        # Parse rates
        rates = _parse_bank_rates(bank_slug, response_data)
        if not rates:
            result["errors"].append("No valid rates found")
            return result
        
        # Store rates in database
        async with SessionLocal() as session:
            repo = BankRatesRepo(session)
            
            # Ensure bank exists
            bank_id = await _ensure_bank_exists(repo, config)
            
            # Add rates
            for code, buy, sell in rates:
                try:
                    await repo.add_rate(bank_id, code, buy, sell)
                    result["rates_collected"] += 1
                    logger.debug(f"Stored {bank_slug} {code}: buy={buy}, sell={sell}")
                except Exception as e:
                    result["errors"].append(f"Failed to store {code}: {e}")
                    logger.error(f"Failed to store {bank_slug} {code}: {e}")
        
        result["success"] = True
        logger.info(f"✅ {bank_slug}: collected {result['rates_collected']} rates")
        
    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"❌ {bank_slug} collection failed: {e}")
    
    return result


async def collect_commercial_banks_rates():
    """Collect rates from all configured commercial banks with monitoring."""
    from core.monitoring import CollectorMonitor
    
    monitor = CollectorMonitor("Commercial Banks")
    monitor.start()
    
    logger.info("🏦 Starting commercial banks rates collection...")
    
    start_time = datetime.utcnow()
    total_banks = len(BANK_CONFIGS)
    successful_banks = 0
    total_rates = 0
    failed_banks = []
    
    # Collect rates from all banks concurrently
    tasks = []
    for bank_slug in BANK_CONFIGS.keys():
        task = asyncio.create_task(collect_bank_rates(bank_slug))
        tasks.append((bank_slug, task))
    
    # Wait for all tasks to complete
    for bank_slug, task in tasks:
        try:
            result = await task
            if result["success"]:
                successful_banks += 1
                total_rates += result["rates_collected"]
            else:
                failed_banks.append({
                    "bank": bank_slug,
                    "errors": result["errors"]
                })
        except Exception as e:
            failed_banks.append({
                "bank": bank_slug, 
                "errors": [str(e)]
            })
    
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    logger.info(
        f"🏦 Commercial banks collection completed in {duration:.1f}s: "
        f"{successful_banks}/{total_banks} banks successful, "
        f"{total_rates} total rates collected"
    )
    
    if failed_banks:
        logger.warning(f"❌ Failed banks: {[b['bank'] for b in failed_banks]}")
        for failure in failed_banks:
            logger.error(f"  {failure['bank']}: {', '.join(failure['errors'])}")
            monitor.record_failure()
    
    # Record metrics
    monitor.record_metric('total_banks', total_banks)
    monitor.record_metric('successful_banks', successful_banks)
    monitor.record_metric('total_rates', total_rates)
    monitor.record_metric('failed_banks_count', len(failed_banks))
    
    # Finish monitoring
    monitor.finish(alert_on_failure=True)
    
    return {
        "total_banks": total_banks,
        "successful_banks": successful_banks, 
        "total_rates": total_rates,
        "failed_banks": failed_banks,
        "duration": duration
    }


if __name__ == "__main__":
    # For standalone testing
    async def test_single_bank():
        # Test a specific bank
        result = await collect_bank_rates("nbu")
        print(f"Test result: {result}")
    
    async def test_all_banks():
        # Test all banks
        result = await collect_commercial_banks_rates()
        print(f"All banks result: {result}")
    
    # Run the test
    asyncio.run(test_all_banks())