from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable


from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable


def get_main_keyboard(i18n: Callable[[str], str], is_subscribed: bool = False) -> ReplyKeyboardMarkup:
    """Create main reply keyboard with localized buttons."""
    # Choose subscribe or unsubscribe button based on current status
    subscribe_button = i18n("button.unsubscribe") if is_subscribed else i18n("button.subscribe")
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n("button.current-rates")),
                KeyboardButton(text=i18n("button.live-rates"))
            ],
            [
                KeyboardButton(text=subscribe_button),
                KeyboardButton(text=i18n("button.language"))
            ]
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard


def get_language_inline_keyboard(i18n: Callable[[str], str]) -> InlineKeyboardMarkup:
    """Create inline keyboard for language selection."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n("lang.uz-cy"), 
                    callback_data="lang:uz_cy"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n("lang.ru"), 
                    callback_data="lang:ru"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n("lang.en"), 
                    callback_data="lang:en"
                )
            ]
        ]
    )
    return keyboard