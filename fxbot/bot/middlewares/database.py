from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.db import SessionLocal
from core.repos import UserRepository, BankRatesRepo


class DatabaseMiddleware(BaseMiddleware):
    """Database middleware for handling user database operations."""
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """Middleware handler to inject database session and user data."""
        async with SessionLocal() as session:
            data["db_session"] = session
            data["user_repo"] = UserRepository(session)
            data["bank_rates_repo"] = BankRatesRepo(session)
            
            # Extract user from different event types
            user = None
            if hasattr(event, 'from_user'):
                # Direct message or callback query
                user = event.from_user
            elif hasattr(event, 'message') and event.message:
                user = event.message.from_user
            elif hasattr(event, 'callback_query') and event.callback_query:
                user = event.callback_query.from_user
            elif hasattr(event, 'inline_query') and event.inline_query:
                user = event.inline_query.from_user
            
            # Get or create user in database
            if user:
                db_user = await data["user_repo"].get_or_create_user(user.id)
                data["db_user"] = db_user
                data["user_lang"] = db_user.lang
            
            return await handler(event, data)