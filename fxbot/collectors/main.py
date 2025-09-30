import asyncio
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from infrastructure.db import init_db
from cbu import collect_cbu_rates

# Load environment variables
load_dotenv()

# Configure logging with enhanced format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/cbu_collector.log') if os.path.exists('logs') else logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def health_monitor():
    """Periodic health monitoring for collectors."""
    while True:
        try:
            await asyncio.sleep(600)  # Every 10 minutes
            logger.info(f"Collector health check - Status: Running, Time: {datetime.now().isoformat()}")
        except Exception as e:
            logger.error(f"Health monitor error: {e}")


async def main():
    """Main function to start the collectors."""
    logger.info("📊 Starting FXBot Collectors...")
    logger.info(f"Collector startup time: {datetime.now().isoformat()}")
    
    try:
        # Initialize database
        await init_db()
        logger.info("✅ Database initialized")
        
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
        logger.info("✅ Scheduler started")
        
        # Start health monitoring
        asyncio.create_task(health_monitor())
        logger.info("✅ Health monitoring started")
        
        # Run initial collection
        logger.info("🔄 Running initial rate collection...")
        await collect_cbu_rates()
        
        # Keep running
        logger.info("🚀 Collectors are now running...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down...")
        finally:
            scheduler.shutdown()
            
    except Exception as e:
        logger.error(f"Error starting collectors: {e}")


if __name__ == "__main__":
    asyncio.run(main())