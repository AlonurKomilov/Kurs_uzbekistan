import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Sentry integration
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import middlewares and handlers
from bot.middlewares import DatabaseMiddleware, I18nMiddleware
from bot.middlewares.error_handler import ErrorHandlerMiddleware, error_handler
from bot.handlers import setup_handlers

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

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/bot.log') if os.path.exists('logs') else logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

# Initialize bot and dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


async def health_monitor():
    """Periodic health monitoring and heartbeat logging for bot."""
    heartbeat_count = 0
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            heartbeat_count += 1
            
            # Heartbeat log with service information
            logger.info(
                f"🔔 Bot heartbeat #{heartbeat_count} - "
                f"Service: bot, Status: Running, "
                f"Time: {datetime.now().isoformat()}, "
                f"Sentry: {'enabled' if SENTRY_DSN else 'disabled'}"
            )
            
            # Additional health metrics every 30 minutes (6 heartbeats)
            if heartbeat_count % 6 == 0:
                logger.info(
                    f"📊 Bot health report - "
                    f"Uptime heartbeats: {heartbeat_count}, "
                    f"Environment: {os.getenv('ENVIRONMENT', 'development')}"
                )
                
        except Exception as e:
            logger.error(f"❌ Health monitor error: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e)


async def main():
    """Main function to start the bot."""
    logger.info("🤖 Starting KUBot...")
    logger.info(f"Bot startup time: {datetime.now().isoformat()}")
    
    try:
        # Initialize database
        from infrastructure.db import init_db
        await init_db()
        logger.info("✅ Database initialized")
        
        # Setup middlewares
        # Error handler middleware comes first
        dp.message.middleware(ErrorHandlerMiddleware())
        dp.callback_query.middleware(ErrorHandlerMiddleware())
        
        # Database middleware must come after error handler to inject session
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
        
        # I18n middleware comes after database to use user language
        dp.message.middleware(I18nMiddleware())
        dp.callback_query.middleware(I18nMiddleware())
        
        # Register global error handler
        dp.errors.register(error_handler)
        
        # Register handlers
        setup_handlers(dp)
        logger.info("✅ Handlers and middlewares registered")
        
        # Initialize and start scheduler
        from bot.scheduler import DigestScheduler
        scheduler = DigestScheduler(bot)
        scheduler.start()
        logger.info("✅ Digest scheduler started")
        
        # Start health monitoring
        asyncio.create_task(health_monitor())
        logger.info("✅ Health monitoring started")
        
        # Start polling
        logger.info("🚀 Bot is now running and polling for updates...")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())