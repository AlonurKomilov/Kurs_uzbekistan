"""
Scheduler for daily digest notifications.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

from core.repos import UserRepository
from core.rates_service import RatesService
from infrastructure.db import get_session


logger = logging.getLogger(__name__)


class DigestScheduler:
    """Scheduler for daily digest notifications."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """Start the scheduler."""
        # Schedule daily digest at 09:00 Asia/Tashkent
        self.scheduler.add_job(
            self.send_daily_digest,
            CronTrigger(hour=9, minute=0, timezone='Asia/Tashkent'),
            id='daily_digest',
            name='Daily Currency Digest',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300  # 5 minutes
        )
        
        self.scheduler.start()
        logger.info("Digest scheduler started - daily digest at 09:00 Asia/Tashkent")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Digest scheduler stopped")
    
    async def send_daily_digest(self):
        """Send daily digest to all subscribed users."""
        logger.info("Starting daily digest broadcast")
        
        try:
            async for session in get_session():
                rates_service = RatesService(session)
                user_repo = UserRepository(session)
                
                # Get rates bundle
                bundle = await rates_service.get_daily_bundle()
                if not bundle:
                    logger.warning("No rates data available for digest")
                    return
                
                # Get all subscribed users
                subscribed_users = await user_repo.get_subscribed_users()
                if not subscribed_users:
                    logger.info("No subscribed users found")
                    return
                
                logger.info(f"Found {len(subscribed_users)} subscribed users")
                
                # Group users by language
                users_by_lang = defaultdict(list)
                for user in subscribed_users:
                    users_by_lang[user.lang].append(user)
                
                # Send digest for each language
                total_sent = 0
                total_errors = 0
                
                for lang, users in users_by_lang.items():
                    sent, errors = await self._send_digest_to_language_group(
                        bundle, lang, users, rates_service
                    )
                    total_sent += sent
                    total_errors += errors
                
                logger.info(
                    f"Daily digest completed: {total_sent} sent, {total_errors} errors"
                )
                
                # Commit session to save any subscription updates
                await session.commit()
                break  # Exit the async generator
                
        except Exception as e:
            logger.error(f"Error in daily digest: {e}", exc_info=True)
    
    async def _send_digest_to_language_group(
        self, 
        bundle: Dict, 
        lang: str, 
        users: List, 
        rates_service: RatesService
    ) -> tuple[int, int]:
        """Send digest to a group of users with the same language."""
        
        logger.info(f"Sending digest to {len(users)} users in language: {lang}")
        
        # Format message for this language
        message_text = rates_service.format_digest_message(bundle, lang)
        keyboard = rates_service.get_digest_keyboard(lang)
        
        sent_count = 0
        error_count = 0
        blocked_users = []
        
        # Send in batches of 500 to avoid overwhelming Telegram
        batch_size = 500
        
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            batch_sent, batch_errors, batch_blocked = await self._send_batch(
                batch, message_text, keyboard, lang
            )
            
            sent_count += batch_sent
            error_count += batch_errors
            blocked_users.extend(batch_blocked)
            
            logger.info(
                f"Batch {i//batch_size + 1} for {lang}: "
                f"{batch_sent} sent, {batch_errors} errors"
            )
            
            # Small delay between batches
            if i + batch_size < len(users):
                await asyncio.sleep(1)
        
        # Remove blocked users from subscriptions
        if blocked_users:
            await self._remove_blocked_subscriptions(blocked_users)
            logger.info(f"Removed {len(blocked_users)} blocked users from subscriptions")
        
        return sent_count, error_count
    
    async def _send_batch(
        self, 
        users: List, 
        message_text: str, 
        keyboard, 
        lang: str
    ) -> tuple[int, int, List]:
        """Send digest to a batch of users."""
        
        sent_count = 0
        error_count = 0
        blocked_users = []
        
        for user in users:
            try:
                await self.bot.send_message(
                    chat_id=user.tg_user_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode=None
                )
                sent_count += 1
                
            except TelegramForbiddenError:
                # User blocked the bot
                blocked_users.append(user)
                logger.debug(f"User {user.tg_user_id} blocked the bot")
                
            except TelegramRetryAfter as e:
                # Rate limiting - wait and retry once
                logger.warning(f"Rate limited, waiting {e.retry_after} seconds")
                await asyncio.sleep(e.retry_after)
                
                try:
                    await self.bot.send_message(
                        chat_id=user.tg_user_id,
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode=None
                    )
                    sent_count += 1
                    
                except Exception as retry_error:
                    logger.error(f"Retry failed for user {user.tg_user_id}: {retry_error}")
                    error_count += 1
                    
            except TelegramBadRequest as e:
                # Invalid chat ID or other client errors
                logger.error(f"Bad request for user {user.tg_user_id}: {e}")
                error_count += 1
                
            except Exception as e:
                # Other errors
                logger.error(f"Error sending to user {user.tg_user_id}: {e}")
                error_count += 1
                
            # Small delay between messages to avoid rate limiting
            await asyncio.sleep(0.1)
        
        return sent_count, error_count, blocked_users
    
    async def _remove_blocked_subscriptions(self, blocked_users: List):
        """Remove subscriptions for blocked users."""
        try:
            async for session in get_session():
                user_repo = UserRepository(session)
                
                for user in blocked_users:
                    await user_repo.update_subscription(user.tg_user_id, False)
                    logger.debug(f"Removed subscription for blocked user {user.tg_user_id}")
                
                await session.commit()
                break  # Exit the async generator
                
        except Exception as e:
            logger.error(f"Error removing blocked subscriptions: {e}")
    
    async def send_test_digest(self, test_user_ids: List[int] | None = None):
        """Send a test digest manually to specific users or all subscribed users."""
        logger.info("Sending test digest")
        
        try:
            async for session in get_session():
                rates_service = RatesService(session)
                user_repo = UserRepository(session)
                
                # Get rates bundle
                bundle = await rates_service.get_daily_bundle()
                if not bundle:
                    logger.warning("No rates data available for test digest")
                    return
                
                # Get target users
                if test_user_ids:
                    # Send to specific test users
                    users = []
                    for user_id in test_user_ids:
                        user = await user_repo.get_or_create_user(user_id)
                        users.append(user)
                else:
                    # Send to all subscribed users
                    users = await user_repo.get_subscribed_users()
                
                if not users:
                    logger.info("No users found for test digest")
                    return
                
                logger.info(f"Sending test digest to {len(users)} users")
                
                # Group by language and send
                users_by_lang = defaultdict(list)
                for user in users:
                    users_by_lang[user.lang].append(user)
                
                for lang, lang_users in users_by_lang.items():
                    await self._send_digest_to_language_group(
                        bundle, lang, lang_users, rates_service
                    )
                
                logger.info("Test digest completed")
                break  # Exit the async generator
                
        except Exception as e:
            logger.error(f"Error in test digest: {e}", exc_info=True)