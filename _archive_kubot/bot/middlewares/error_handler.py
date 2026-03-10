"""Error handling middleware for bot."""
import logging
import traceback
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, ErrorEvent
import sentry_sdk
import os

logger = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN")


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware for catching and logging errors."""
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """Wrap handler with error handling."""
        try:
            return await handler(event, data)
        except Exception as e:
            # Log the error
            logger.error(
                f"Error handling update: {e}\n"
                f"Traceback: {traceback.format_exc()}",
                exc_info=True
            )
            
            # Send to Sentry if configured
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e)
            
            # Try to notify user if possible
            try:
                if hasattr(event, 'answer'):
                    await event.answer(
                        "❌ An error occurred. Please try again later.",
                        show_alert=True
                    )
                elif hasattr(event, 'message') and event.message:
                    await event.message.answer(
                        "❌ An error occurred. Please try again later."
                    )
            except Exception as notify_error:
                logger.error(f"Failed to notify user about error: {notify_error}")
            
            # Re-raise to let aiogram handle it
            raise


async def error_handler(event: ErrorEvent):
    """Global error handler for aiogram."""
    logger.error(
        f"Critical error: {event.exception}\n"
        f"Update: {event.update}",
        exc_info=event.exception
    )
    
    # Send to Sentry if configured
    if SENTRY_DSN:
        sentry_sdk.capture_exception(event.exception)
