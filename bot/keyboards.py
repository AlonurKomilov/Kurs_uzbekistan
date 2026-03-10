"""Keyboards: main reply keyboard, language inline, currency tabs + pagination."""

from __future__ import annotations

from typing import Callable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

CURRENCIES = ("USD", "EUR", "RUB")


def main_keyboard(i18n: Callable, is_subscribed: bool = False) -> ReplyKeyboardMarkup:
    sub_btn = i18n("button.unsubscribe") if is_subscribed else i18n("button.subscribe")
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n("button.current-rates"))],
            [KeyboardButton(text=sub_btn), KeyboardButton(text=i18n("button.language"))],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def language_keyboard(i18n: Callable) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=i18n("lang.uz-cy"), callback_data="lang:uz_cy")],
            [InlineKeyboardButton(text=i18n("lang.ru"), callback_data="lang:ru")],
            [InlineKeyboardButton(text=i18n("lang.en"), callback_data="lang:en")],
        ]
    )


def digest_schedule_keyboard(i18n: Callable) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=i18n("schedule.morning"), callback_data="sched:morning")],
            [InlineKeyboardButton(text=i18n("schedule.evening"), callback_data="sched:evening")],
            [InlineKeyboardButton(text=i18n("schedule.twice"), callback_data="sched:twice")],
            [InlineKeyboardButton(text=i18n("schedule.off"), callback_data="sched:off")],
        ]
    )


def currency_tabs(
    currency: str,
    current_page: int = 1,
    total_pages: int = 1,
    show_all: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Currency tab row
    tab_row: list[InlineKeyboardButton] = []
    for c in CURRENCIES:
        label = f"{'🔸' if c == currency else '▫️'} {c}"
        tab_row.append(
            InlineKeyboardButton(text=label, callback_data=f"cr:{c}:{'all' if show_all else 'top'}")
        )
    rows.append(tab_row)

    if show_all and total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if current_page > 1:
            nav.append(
                InlineKeyboardButton(text="◀️", callback_data=f"cr:{currency}:p{current_page - 1}")
            )
        nav.append(
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop")
        )
        if current_page < total_pages:
            nav.append(
                InlineKeyboardButton(text="▶️", callback_data=f"cr:{currency}:p{current_page + 1}")
            )
        rows.append(nav)
        rows.append(
            [InlineKeyboardButton(text="🔝", callback_data=f"cr:{currency}:top")]
        )
    elif show_all:
        rows.append(
            [InlineKeyboardButton(text="🔝", callback_data=f"cr:{currency}:top")]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text="📋 Show All", callback_data=f"cr:{currency}:all")]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)
