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
    # Show welcome message with main keyboard
    keyboard = get_main_keyboard(i18n)
    
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
    lang_code = callback_query.data.split(":")[1]
    
    # Update user language in database
    await user_repo.update_language(callback_query.from_user.id, lang_code)
    
    # Get updated i18n function for new language
    from bot.middlewares.i18n import I18nMiddleware
    i18n_middleware = I18nMiddleware()
    new_i18n = lambda key, **kwargs: i18n_middleware.get_text(lang_code, key, **kwargs)
    
    # Create new keyboard with updated language
    keyboard = get_main_keyboard(new_i18n)
    
    # Answer callback and update message
    await callback_query.answer(new_i18n("lang.saved"))
    
    # Edit the original message to remove inline keyboard and send new keyboard
    await callback_query.message.edit_text(new_i18n("lang.saved"))
    
    # Send new keyboard as a new message
    await callback_query.message.answer(
        text=new_i18n("start.welcome"),
        reply_markup=keyboard
    )


# Handlers for keyboard buttons
@router.message(lambda message: message.text and ("Current Rates" in message.text or "Ҳозирги курслар" in message.text or "Текущие курсы" in message.text))
async def current_rates_handler(message: Message, i18n, **kwargs):
    """Handle current rates button."""
    await message.answer(i18n("currency-rates") + " - " + i18n("loading"))


@router.message(lambda message: message.text and ("Today's Rates" in message.text or "Бугунги курслар" in message.text or "Курсы на сегодня" in message.text))
async def today_rates_handler(message: Message, i18n, **kwargs):
    """Handle today's rates button."""
    await message.answer(i18n("currency-rates") + " - " + i18n("loading"))


@router.message(lambda message: message.text and ("Subscribe" in message.text or "Обуна бўлиш" in message.text or "Подписаться" in message.text))
async def subscribe_handler(message: Message, i18n, **kwargs):
    """Handle subscribe button."""
    await message.answer(i18n("button.subscribe") + " - " + i18n("loading"))


@router.message(lambda message: message.text and ("Language" in message.text or "Тил" in message.text or "Язык" in message.text))
async def language_button_handler(message: Message, i18n, **kwargs):
    """Handle language button."""
    keyboard = get_language_inline_keyboard(i18n)
    
    await message.answer(
        text=i18n("lang.select"),
        reply_markup=keyboard
    )