import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Sentry integration
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.db import init_db
from cbu import collect_cbu_rates
from commercial_banks import collect_commercial_banks_rates

# Load environment variables
load_dotenv()

# Initialize Sentry if DSN is provided
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "development"),
    )

# Configure logging with enhanced format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/collectors.log') if os.path.exists('logs') else logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def health_monitor():
    """Periodic health monitoring and heartbeat logging for collectors."""
    heartbeat_count = 0
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            heartbeat_count += 1
            
            # Heartbeat log with service information
            logger.info(
                f"🔔 Collector heartbeat #{heartbeat_count} - "
                f"Service: collectors, Status: Running, "
                f"Time: {datetime.now().isoformat()}, "
                f"Sentry: {'enabled' if SENTRY_DSN else 'disabled'}"
            )
            
            # Additional health metrics every 30 minutes (6 heartbeats)
            if heartbeat_count % 6 == 0:
                logger.info(
                    f"📊 Collector health report - "
                    f"Uptime heartbeats: {heartbeat_count}, "
                    f"Environment: {os.getenv('ENVIRONMENT', 'development')}"
                )
                
        except Exception as e:
            logger.error(f"❌ Health monitor error: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e)


async def main():
    """Main function to start the collectors."""
    logger.info("📊 Starting KUBot Collectors...")
    logger.info(f"Collector startup time: {datetime.now().isoformat()}")
    
    try:
        # Initialize database
        await init_db()
        logger.info("✅ Database initialized")
        
        # Create scheduler
        scheduler = AsyncIOScheduler()
        
        # Add CBU rates collection job (every 30 minutes)
        scheduler.add_job(
            collect_cbu_rates,
            IntervalTrigger(minutes=30),
            id='cbu_rates_collector',
            name='CBU Rates Collector'
        )
        
        # Add commercial banks rates collection job (every 15 minutes for more frequent updates)
        scheduler.add_job(
            collect_commercial_banks_rates,
            IntervalTrigger(minutes=15),
            id='commercial_banks_collector',
            name='Commercial Banks Rates Collector'
        )
        
        # Start scheduler
        scheduler.start()
        logger.info("✅ Scheduler started with CBU + Commercial Banks collectors")
        
        # Start health monitoring
        asyncio.create_task(health_monitor())
        logger.info("✅ Health monitoring started")
        
        # Run initial collections
        logger.info("🔄 Running initial rate collections...")
        
        # Run CBU collection first
        await collect_cbu_rates()
        
        # Run commercial banks collection
        await collect_commercial_banks_rates()
        
        # Keep running
        logger.info("🚀 Collectors are now running with enhanced bank coverage...")
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