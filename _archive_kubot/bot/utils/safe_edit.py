# bot/utils/safe_edit.py
import hashlib
from aiogram.exceptions import TelegramBadRequest
from logging import getLogger
from core.repos import DashboardsRepo

log = getLogger(__name__)

def compute_hash(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

async def safe_edit(bot, repo: DashboardsRepo, dashboard, new_text: str, reply_markup=None):
    """
    Safely edit a message with content hashing and fallback handling.
    
    Args:
        bot: Aiogram bot instance
        repo: DashboardsRepo instance
        dashboard: Dashboard model instance
        new_text: New message text
        reply_markup: Optional reply markup
        
    Returns:
        bool: True if message was actually updated, False if no change needed
    """
    # Compute hash of new content
    new_hash = compute_hash(new_text)
    
    # Skip if content hasn't changed
    if dashboard.last_hash == new_hash:
        log.debug(f"Content unchanged for dashboard {dashboard.id}, skipping edit")
        return False  # no change
    
    try:
        # Attempt to edit the existing message
        await bot.edit_message_text(
            chat_id=dashboard.chat_id, 
            message_id=dashboard.message_id,
            text=new_text, 
            reply_markup=reply_markup, 
            disable_web_page_preview=True
        )
        
        # Update hash in database
        await repo.update_hash(dashboard.id, new_hash)
        log.debug(f"Successfully edited message for dashboard {dashboard.id}")
        return True
        
    except TelegramBadRequest as e:
        msg = str(e).lower()
        
        if "message is not modified" in msg:
            # Telegram says content is the same, treat as successfully updated
            await repo.update_hash(dashboard.id, new_hash)
            log.debug(f"Message not modified for dashboard {dashboard.id}, updating hash anyway")
            return False
            
        elif "message to edit not found" in msg or "message can't be edited" in msg:
            # Original message was deleted, create a new one
            log.info(f"Original message not found for dashboard {dashboard.id}, creating new message")
            try:
                new_message = await bot.send_message(
                    chat_id=dashboard.chat_id, 
                    text=new_text, 
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
                
                # Update database with new message ID and hash
                await repo.replace_message_id(dashboard.id, new_message.message_id, new_hash)
                log.info(f"Created new message {new_message.message_id} for dashboard {dashboard.id}")
                return True
                
            except Exception as send_error:
                log.error(f"Failed to send new message for dashboard {dashboard.id}: {send_error}")
                raise
        else:
            # Other errors - log and re-raise
            log.exception(f"safe_edit failed for dashboard {dashboard.id}: {msg}")
            raise