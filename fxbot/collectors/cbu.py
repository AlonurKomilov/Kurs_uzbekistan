import logging
import httpx
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.db import SessionLocal

logger = logging.getLogger(__name__)

# CBU API endpoint
CBU_API_URL = "https://cbu.uz/oz/arkhiv-kursov-valyut/json/"


async def collect_cbu_rates():
    """Collect currency rates from Central Bank of Uzbekistan."""
    logger.info("Collecting CBU rates...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(CBU_API_URL)
            response.raise_for_status()
            
            rates_data = response.json()
            
            # Process and store rates
            async with SessionLocal() as session:
                await process_rates(session, rates_data)
                
        logger.info(f"Successfully collected {len(rates_data)} rates from CBU")
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error collecting CBU rates: {e}")
    except Exception as e:
        logger.error(f"Error collecting CBU rates: {e}")


async def process_rates(session: AsyncSession, rates_data: list):
    """Process and store currency rates in database."""
    # Placeholder for actual database operations
    # This would typically involve:
    # 1. Parsing the rates data
    # 2. Creating or updating database records
    # 3. Committing the transaction
    
    logger.info(f"Processing {len(rates_data)} currency rates")
    
    for rate in rates_data:
        logger.debug(f"Rate: {rate.get('Ccy', 'Unknown')} = {rate.get('Rate', 'N/A')}")
        
    # Commit changes
    await session.commit()