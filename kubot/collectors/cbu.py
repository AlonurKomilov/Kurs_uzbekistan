import asyncio
import sys
from pathlib import Path
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.repos import CbuRatesRepo, BankRatesRepo

logger = logging.getLogger(__name__)

# CBU API endpoint
CBU_URL = "https://cbu.uz/oz/arkhiv-kursov-valyut/json/"

# Supported currency codes we want to track
SUPPORTED_CURRENCIES = {"USD", "EUR", "RUB", "GBP", "JPY", "CHF", "KRW", "CNY"}


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True
)
async def _fetch_cbu_data():
    """Fetch CBU rates with retry mechanism."""
    logger.info("Fetching CBU rates from API...")
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(CBU_URL)
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"Successfully fetched {len(data)} currency records from CBU")
        return data


async def collect_cbu_rates():
    """Collect and store CBU rates with robust error handling."""
    logger.info("Starting CBU rates collection...")
    
    try:
        # Fetch data with retries
        data = await _fetch_cbu_data()
        
        if not data:
            logger.warning("No data received from CBU API")
            return
        
        # Initialize repository with session
        from infrastructure.db import SessionLocal
        
        async with SessionLocal() as session:
            cbu_repo = CbuRatesRepo(session)
            bank_repo = BankRatesRepo(session)
            
            # Get CBU bank record once
            cbu_bank = await bank_repo.get_bank_by_slug('cbu')
            if not cbu_bank:
                logger.warning("CBU bank not found in database. Rates will only be stored in cbu_rates table.")
            
            # Process each rate record
            successful_inserts = 0
            failed_inserts = 0
            fetched_at = datetime.utcnow()
            
            for row in data:
                try:
                    # Extract and validate required fields
                    code = _extract_currency_code(row)
                    rate = _extract_rate(row)
                    date_str = _extract_date(row)
                    
                    # Skip if we don't track this currency or data is invalid
                    if not code or code not in SUPPORTED_CURRENCIES:
                        continue
                        
                    if rate is None or rate <= 0:
                        logger.warning(f"Invalid rate for {code}: {rate}")
                        continue
                    
                    # Store in cbu_rates table (original functionality)
                    await cbu_repo.upsert_rate(
                        code=code,
                        rate=rate,
                        date_str=date_str,
                        fetched_at=fetched_at
                    )
                    
                    # Also store in bank_rates table for TWA compatibility
                    if cbu_bank:
                        await bank_repo.add_rate(
                            bank_id=cbu_bank.id,  # type: ignore
                            code=code,
                            buy=rate,  # CBU official rates - buy/sell are the same
                            sell=rate
                        )
                    
                    successful_inserts += 1
                    logger.debug(f"Stored {code}: {rate}")
                    
                except Exception as e:
                    failed_inserts += 1
                    logger.error(f"Failed to process CBU row {row}: {e}")
                    continue
            
            logger.info(
                f"CBU rates collection completed: "
                f"{successful_inserts} successful, {failed_inserts} failed"
            )
        
    except Exception as e:
        logger.error(f"CBU rates collection failed: {e}", exc_info=True)
        raise


def _extract_currency_code(row: dict) -> str | None:
    """Extract currency code from CBU API response row."""
    code = row.get("Ccy") or row.get("code") or row.get("Currency")
    return code.upper() if code else None


def _extract_rate(row: dict) -> float | None:
    """Extract exchange rate from CBU API response row."""
    rate_value = row.get("Rate") or row.get("rate") or row.get("Nominal")
    
    if rate_value is None:
        return None
    
    try:
        return float(rate_value)
    except (ValueError, TypeError):
        return None


def _extract_date(row: dict) -> str | None:
    """Extract date from CBU API response row."""
    return row.get("Date") or row.get("date") or None


if __name__ == "__main__":
    # For standalone testing
    asyncio.run(collect_cbu_rates())