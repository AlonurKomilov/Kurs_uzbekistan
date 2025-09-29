import asyncio
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from infrastructure.db import init_db
from cbu import collect_cbu_rates

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main function to start the collectors."""
    logger.info("Starting FXBot Collectors...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Create scheduler
        scheduler = AsyncIOScheduler()
        
        # Add jobs
        scheduler.add_job(
            collect_cbu_rates,
            IntervalTrigger(minutes=30),  # Collect every 30 minutes
            id='cbu_rates_collector',
            name='CBU Rates Collector'
        )
        
        # Start scheduler
        scheduler.start()
        logger.info("Scheduler started")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            scheduler.shutdown()
            
    except Exception as e:
        logger.error(f"Error starting collectors: {e}")


if __name__ == "__main__":
    asyncio.run(main())