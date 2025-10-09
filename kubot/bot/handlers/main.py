import sys
from pathlib import Path
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bot.keyboards.main import get_main_keyboard, get_language_inline_keyboard
from core.repos import UserRepository

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message, i18n, user_repo: UserRepository, **kwargs):
    """Handle /start command."""
    if not message.from_user:
        return
        
    # Get or create user to check subscription status
    user = await user_repo.get_or_create_user(message.from_user.id)
    
    # Show welcome message with main keyboard
    keyboard = get_main_keyboard(i18n, bool(user.subscribed))
    
    await message.answer(
        text=i18n("start.welcome"),
        reply_markup=keyboard
    )


@router.message(Command("language"))
async def language_handler(message: Message, i18n, **kwargs):
    """Handle /language command."""
    keyboard = get_language_inline_keyboard(i18n)
    
    await message.answer(
        text=i18n("lang.select"),
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data and c.data.startswith("lang:"))
async def language_callback_handler(callback_query: CallbackQuery, i18n, user_repo: UserRepository, **kwargs):
    """Handle language selection callback."""
    # Extract language code from callback data
    if not callback_query.data:
        return
    lang_code = callback_query.data.split(":")[1]
    
    # Update user language in database
    if not callback_query.from_user:
        return
    await user_repo.update_language(callback_query.from_user.id, lang_code)
    
    # Get updated i18n function for new language
    from bot.middlewares.i18n import I18nMiddleware
    i18n_middleware = I18nMiddleware()
    new_i18n = lambda key, **kwargs: i18n_middleware.get_text(lang_code, key, **kwargs)
    
    # Create new keyboard with updated language
    keyboard = get_main_keyboard(new_i18n, False)  # Default to False, will be updated if needed
    
    # Answer callback and update message
    await callback_query.answer(new_i18n("lang.saved"))
    
    # Edit message if it's a callback, send new if it's a command
    if callback_query.message and hasattr(callback_query.message, 'edit_text'):
        try:
            from aiogram.types import Message
            if isinstance(callback_query.message, Message):
                await callback_query.message.edit_text(
                    new_i18n("start.welcome"),
                    reply_markup=None  # Remove inline markup since we're using reply keyboard
                )
        except Exception:
            # Fallback to sending new message
            await callback_query.message.answer(
                text=new_i18n("start.welcome"),
                reply_markup=keyboard
            )
    elif callback_query.message:
        # Send new keyboard as a new message
        await callback_query.message.answer(
            text=new_i18n("start.welcome"),
            reply_markup=keyboard
        )


# Handlers for keyboard buttons
@router.message(lambda message: message.text and ("Current Rates" in message.text or "Ҳозирги курс" in message.text or "Текущий курс" in message.text))
async def current_rates_handler(message: Message, i18n, **kwargs):
    """Handle current rates button."""
    await message.answer(i18n("currency-rates") + " - " + i18n("loading"))


@router.message(lambda message: message.text and ("Live Rates" in message.text or "Жонли курс" in message.text or "Живой курс" in message.text))
async def live_rates_handler(message: Message, i18n, user_repo: UserRepository, **kwargs):
    """Handle live rates button - opens TWA with user's language."""
    if not message.from_user:
        return
        
    # Get user to fetch their language preference
    user = await user_repo.get_or_create_user(message.from_user.id)
    
    # Get validated TWA base URL from environment
    import os
    from core.validation import get_validated_twa_url
    twa_base_url = get_validated_twa_url(os.getenv("TWA_BASE_URL", ""))
    
    # Create TWA URL with user's language
    twa_url = f"{twa_base_url}/twa?lang={user.lang}"
    
    # Create inline keyboard with Web App button
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n("button.live-rates"),
                    web_app=WebAppInfo(url=twa_url)
                )
            ]
        ]
    )
    
    await message.answer(
        text=i18n("button.live-rates"),
        reply_markup=keyboard
    )


@router.message(lambda message: message.text and (
    "Subscribe" in message.text or 
    "Unsubscribe" in message.text or
    "Обуна" in message.text or  # Uzbek
    "беков" in message.text or
    "Подписаться" in message.text or  # Russian
    "Отписаться" in message.text
))
async def subscription_handler(message: Message, i18n, user_repo: UserRepository):
    """Handle subscription toggle."""
    if not message.from_user:
        return
    
    try:
        user = await user_repo.toggle_subscription(message.from_user.id)
        
        if user:
            # Update keyboard with new subscription status
            is_subscribed = bool(user.subscribed)
            keyboard = get_main_keyboard(i18n, is_subscribed)
            
            # Send appropriate message
            if is_subscribed:
                await message.answer(
                    text=i18n("subscription.enabled"),
                    reply_markup=keyboard
                )
            else:
                await message.answer(
                    text=i18n("subscription.disabled"),
                    reply_markup=keyboard
                )
        else:
            await message.answer(i18n("subscription.error"))
            
    except Exception as e:
        await message.answer(i18n("subscription.error"))


@router.message(lambda message: message.text and ("Language" in message.text or "Тил" in message.text or "Язык" in message.text))
async def language_button_handler(message: Message, i18n, **kwargs):
    """Handle language button."""
    keyboard = get_language_inline_keyboard(i18n)
    
    await message.answer(
        text=i18n("lang.select"),
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "refresh_rates")
async def refresh_rates_callback(callback_query: CallbackQuery, i18n, **kwargs):
    """Handle refresh rates callback from digest message."""
    try:
        from core.rates_service import get_rates_service
        
        # Get fresh rates
        rates_service = await get_rates_service()
        bundle = await rates_service.get_daily_bundle()
        
        # Format new digest message  
        fresh_digest = rates_service.format_digest_message(bundle, i18n.locale)
        keyboard = rates_service.get_digest_keyboard(i18n.locale)
        
        # Update the message
        from aiogram.types import Message
        if isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                text=fresh_digest,
                reply_markup=keyboard
            )
        
        await callback_query.answer(i18n("button.refresh"))
        
    except Exception as e:
        await callback_query.answer(i18n("error-occurred").format(error=str(e)))