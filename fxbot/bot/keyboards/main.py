from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable


def get_main_keyboard(i18n: Callable[[str], str]) -> ReplyKeyboardMarkup:
    """Create main reply keyboard with localized buttons."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n("button.current-rates")),
                KeyboardButton(text=i18n("button.today-rates"))
            ],
            [
                KeyboardButton(text=i18n("button.subscribe")),
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