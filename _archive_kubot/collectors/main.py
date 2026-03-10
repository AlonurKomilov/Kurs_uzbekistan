import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# Sentry integration
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from infrastructure.db import init_db
from cbu import collect_cbu_rates

# Import individual bank collectors
from kapitalbank import collect as collect_kapitalbank
from nbu import collect as collect_nbu
from ipoteka import collect as collect_ipoteka
from hamkorbank import collect as collect_hamkorbank
from tbc import collect as collect_tbc
from turonbank import collect as collect_turonbank
from universal import collect as collect_universal


async def cleanup_old_rates():
    """Delete bank_rates older than retention period to prevent unbounded table growth."""
    from infrastructure.db import get_session_context
    from sqlalchemy import delete
    from core.models import BankRate

    retention_days = int(os.getenv("BANK_RATES_RETENTION_DAYS", "90"))
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    try:
        async with get_session_context() as session:
            result = await session.execute(
                delete(BankRate).where(BankRate.fetched_at < cutoff)
            )
            deleted = result.rowcount
            if deleted:
                logger.info(f"🗑️ Deleted {deleted} bank_rates older than {retention_days} days")
    except Exception as e:
        logger.error(f"❌ Retention cleanup failed: {e}")

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
_log_handlers = [logging.StreamHandler(sys.stdout)]
if os.path.exists('logs'):
    _log_handlers.append(logging.FileHandler('logs/collectors.log'))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=_log_handlers,
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

        # Add daily retention cleanup at 03:00 Tashkent time
        scheduler.add_job(
            cleanup_old_rates,
            CronTrigger(hour=3, minute=0, timezone='Asia/Tashkent'),
            id='retention_cleanup',
            name='Data Retention Cleanup',
            max_instances=1,
            coalesce=True,
        )
        
        # Add individual bank collectors (every 15 minutes each, staggered)
        scheduler.add_job(
            collect_kapitalbank,
            IntervalTrigger(minutes=15),
            id='kapitalbank_collector',
            name='Kapitalbank Collector'
        )
        
        scheduler.add_job(
            collect_nbu,
            IntervalTrigger(minutes=15),
            id='nbu_collector',
            name='NBU Collector'
        )
        
        scheduler.add_job(
            collect_ipoteka,
            IntervalTrigger(minutes=15),
            id='ipoteka_collector',
            name='Ipoteka Collector'
        )
        
        scheduler.add_job(
            collect_hamkorbank,
            IntervalTrigger(minutes=15),
            id='hamkorbank_collector',
            name='Hamkorbank Collector'
        )
        
        scheduler.add_job(
            collect_tbc,
            IntervalTrigger(minutes=15),
            id='tbc_collector',
            name='TBC Collector'
        )
        
        scheduler.add_job(
            collect_turonbank,
            IntervalTrigger(minutes=15),
            id='turonbank_collector',
            name='Turonbank Collector'
        )
        
        scheduler.add_job(
            collect_universal,
            IntervalTrigger(minutes=15),
            id='universal_collector',
            name='Universal Collector'
        )
        
        # Start scheduler
        scheduler.start()
        logger.info("✅ Scheduler started with CBU + Individual Bank collectors")
        
        # Start health monitoring
        asyncio.create_task(health_monitor())
        logger.info("✅ Health monitoring started")
        
        # Run initial collections
        logger.info("🔄 Running initial rate collections...")
        
        # Run CBU collection first
        await collect_cbu_rates()
        
        # Run all individual bank collections in parallel
        await asyncio.gather(
            collect_kapitalbank(),
            collect_nbu(),
            collect_ipoteka(),
            collect_hamkorbank(),
            collect_tbc(),
            collect_turonbank(),
            collect_universal(),
            return_exceptions=True  # Don't let one failure stop others
        )
        
        # Keep running
        logger.info("🚀 Collectors are now running (CBU + 7 commercial banks: Kapitalbank, NBU, Ipoteka, Hamkorbank, TBC, Turonbank, Universal)...")
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