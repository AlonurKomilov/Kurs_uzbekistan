import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import middlewares and handlers
from bot.middlewares import DatabaseMiddleware, I18nMiddleware
from bot.handlers import setup_handlers

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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


async def main():
    """Main function to start the bot."""
    logger.info("Starting FXBot...")
    
    try:
        # Initialize database
        from infrastructure.db import init_db
        await init_db()
        logger.info("Database initialized")
        
        # Setup middlewares
        # Database middleware must come first to inject session
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
        
        # I18n middleware comes after database to use user language
        dp.message.middleware(I18nMiddleware())
        dp.callback_query.middleware(I18nMiddleware())
        
        # Register handlers
        setup_handlers(dp)
        logger.info("Handlers and middlewares registered")
        
        # Start polling
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())