"""Daily digest sending with batching, retry, and error handling."""

import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from decimal import Decimal

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.repos import UserRepository, CbuRatesRepo
from infrastructure.db import get_session

logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT = None  # Will be initialized when needed
BATCH_SIZE = 500  # Send messages in batches to avoid rate limits


def get_bot() -> Bot:
    """Get bot instance, initializing if needed."""
    global BOT
    if BOT is None:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        BOT = Bot(token=BOT_TOKEN)
    return BOT

# Retry configuration for Telegram API calls
@retry(
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((TelegramRetryAfter, ConnectionError, TimeoutError))
)
async def send_message_safe(chat_id: int, text: str, **kwargs) -> bool:
    """Send message with retry logic for rate limits and network errors."""
    try:
        bot = get_bot()
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        # User blocked bot or chat not found - don't retry
        logger.warning(f"Failed to send to {chat_id}: {e}")
        return False
    except TelegramRetryAfter as e:
        # Rate limit hit - tenacity will retry with backoff
        logger.info(f"Rate limited for {e.retry_after} seconds, will retry")
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending to {chat_id}: {e}")
        return False


def render_digest_for_lang(lang: str, rates_data: Dict[str, Any]) -> str:
    """Render daily digest message for specific language."""
    
    # Language-specific templates
    templates = {
        "uz_cy": {
            "title": "📈 Кунлик валюта курси",
            "date": "📅 Сана: {date}",
            "usd": "💵 АҚШ доллари: {rate} сўм",
            "eur": "💶 Евро: {rate} сўм", 
            "rub": "🇷🇺 Рубль: {rate} сўм",
            "trend_up": "📈 ({change:+.2f})",
            "trend_down": "📉 ({change:+.2f})",
            "trend_same": "➡️ (0.00)",
            "footer": "\n🔄 Маълумотлар ЎРБ дан олинган\n📱 /rates - барча курслар"
        },
        "ru": {
            "title": "📈 Ежедневный курс валют",
            "date": "📅 Дата: {date}",
            "usd": "💵 Доллар США: {rate} сум",
            "eur": "💶 Евро: {rate} сум",
            "rub": "🇷🇺 Рубль: {rate} сум", 
            "trend_up": "📈 ({change:+.2f})",
            "trend_down": "📉 ({change:+.2f})",
            "trend_same": "➡️ (0.00)",
            "footer": "\n🔄 Данные от ЦБ РУз\n📱 /rates - все курсы"
        },
        "en": {
            "title": "📈 Daily Currency Rates",
            "date": "📅 Date: {date}",
            "usd": "💵 US Dollar: {rate} som",
            "eur": "💶 Euro: {rate} som",
            "rub": "🇷🇺 Ruble: {rate} som",
            "trend_up": "📈 ({change:+.2f})",
            "trend_down": "📉 ({change:+.2f})",
            "trend_same": "➡️ (0.00)",
            "footer": "\n🔄 Data from CBU\n📱 /rates - all rates"
        }
    }
    
    t = templates.get(lang, templates["en"])
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Build message
    lines = [
        t["title"],
        t["date"].format(date=today),
        ""
    ]
    
    # Add currency rates with trends
    for code in ["USD", "EUR", "RUB"]:
        if code in rates_data:
            rate = rates_data[code]["rate"]
            change = rates_data[code].get("change", 0)
            
            rate_line = t[code.lower()].format(rate=f"{rate:,.0f}")
            
            # Add trend indicator
            if change > 0:
                rate_line += " " + t["trend_up"].format(change=change)
            elif change < 0:
                rate_line += " " + t["trend_down"].format(change=change)
            else:
                rate_line += " " + t["trend_same"]
                
            lines.append(rate_line)
    
    lines.append(t["footer"])
    
    return "\n".join(lines)


async def get_daily_rates_data() -> Dict[str, Any]:
    """Get current rates data for digest."""
    async for session in get_session():
        cbu_repo = CbuRatesRepo(session)
        
        # Get latest rates for main currencies
        rates_data = {}
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        for code in ["USD", "EUR", "RUB"]:
            # Get today's rate
            today_rate = await cbu_repo.get_latest_by_code(code)
            if today_rate and today_rate.rate is not None:
                rates_data[code] = {
                    "rate": float(today_rate.rate),
                    "change": 0  # Default to 0 if no comparison
                }
                
                # Try to get yesterday's rate for comparison
                yesterday_rate = await cbu_repo.get_by_code_and_date(code, yesterday)
                if yesterday_rate and yesterday_rate.rate is not None:
                    change = float(today_rate.rate) - float(yesterday_rate.rate)
                    rates_data[code]["change"] = change
        
        return rates_data
    
    # Fallback if no session available
    return {}


async def send_daily_digest() -> Dict[str, Any]:
    """Send daily digest to all subscribed users, grouped by language."""
    start_time = datetime.now()
    stats = {
        "started_at": start_time.isoformat(),
        "total_users": 0,
        "successful_sends": 0,
        "failed_sends": 0,
        "blocked_users": 0,
        "languages": {},
        "batches_processed": 0
    }
    
    try:
        # Get rates data
        logger.info("📊 Fetching daily rates data...")
        rates_data = await get_daily_rates_data()
        
        if not rates_data:
            logger.warning("⚠️ No rates data available for digest")
            return stats
        
        # Get subscribers grouped by language
        groups = {}
        async for session in get_session():
            users_repo = UserRepository(session)
            groups = await users_repo.get_subscribers_grouped_by_lang()
            break  # Exit after first session
        
        if not groups:
            logger.info("📭 No subscribed users found")
            return stats
        
        total_users = sum(len(tg_ids) for tg_ids in groups.values())
        stats["total_users"] = total_users
        
        logger.info(f"📨 Starting digest send to {total_users} users in {len(groups)} languages")
        
        # Process each language group
        for lang, tg_ids in groups.items():
            logger.info(f"🌐 Processing {len(tg_ids)} users for language: {lang}")
            
            # Render message for this language
            message_text = render_digest_for_lang(lang, rates_data)
            
            # Initialize language stats
            stats["languages"][lang] = {
                "total": len(tg_ids),
                "successful": 0,
                "failed": 0,
                "blocked": 0
            }
            
            # Send in batches to manage rate limits
            for i in range(0, len(tg_ids), BATCH_SIZE):
                batch = tg_ids[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (len(tg_ids) + BATCH_SIZE - 1) // BATCH_SIZE
                
                logger.info(f"📦 Processing batch {batch_num}/{total_batches} for {lang} ({len(batch)} users)")
                
                # Send messages concurrently within batch
                tasks = [
                    send_message_safe(
                        chat_id=uid,
                        text=message_text,
                        disable_web_page_preview=True,
                        parse_mode="HTML"
                    )
                    for uid in batch
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle blocked users
                async for session in get_session():
                    users_repo = UserRepository(session)
                    
                    for uid, success in zip(batch, results):
                        if success is True:
                            stats["successful_sends"] += 1
                            stats["languages"][lang]["successful"] += 1
                        else:
                            stats["failed_sends"] += 1
                            stats["languages"][lang]["failed"] += 1
                            
                            # If user blocked bot, soft unsubscribe them
                            if isinstance(success, Exception):
                                logger.info(f"🚫 Soft unsubscribing blocked user: {uid}")
                                await users_repo.soft_unsubscribe(uid)
                                stats["blocked_users"] += 1
                                stats["languages"][lang]["blocked"] += 1
                    break  # Exit after first session
                
                stats["batches_processed"] += 1
                
                # Small pause between batches to be nice to Telegram API
                if i + BATCH_SIZE < len(tg_ids):  # Don't sleep after last batch
                    await asyncio.sleep(1)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = duration
        
        logger.info(
            f"✅ Digest sending completed in {duration:.1f}s. "
            f"Success: {stats['successful_sends']}/{stats['total_users']}, "
            f"Blocked: {stats['blocked_users']}, "
            f"Failed: {stats['failed_sends']}"
        )
        
    except Exception as e:
        logger.error(f"❌ Error during digest sending: {e}")
        stats["error"] = str(e)
    
    return stats


async def cleanup():
    """Cleanup resources."""
    try:
        if BOT is not None and hasattr(BOT, 'session') and BOT.session:
            await BOT.session.close()
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # For testing purposes
    logging.basicConfig(level=logging.INFO)
    asyncio.run(send_daily_digest())