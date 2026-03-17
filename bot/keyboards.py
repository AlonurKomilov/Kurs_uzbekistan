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
            [KeyboardButton(text=i18n("button.converter"))],
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


def converter_currency_keyboard(i18n: Callable) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 USD", callback_data="conv:USD"),
                InlineKeyboardButton(text="💶 EUR", callback_data="conv:EUR"),
                InlineKeyboardButton(text="₽ RUB", callback_data="conv:RUB"),
            ]
        ]
    )


def currency_tabs(
    currency: str,
    current_page: int = 1,
    total_pages: int = 1,
    show_all: bool = False,
    i18n: Callable | None = None,
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
        _top = i18n("button.back-to-top") if i18n else "🔝"
        rows.append(
            [InlineKeyboardButton(text=_top, callback_data=f"cr:{currency}:top")]
        )
    elif show_all:
        _top = i18n("button.back-to-top") if i18n else "🔝"
        rows.append(
            [InlineKeyboardButton(text=_top, callback_data=f"cr:{currency}:top")]
        )
    else:
        _show = i18n("button.show-all") if i18n else "📋 Show All"
        rows.append(
            [InlineKeyboardButton(text=_show, callback_data=f"cr:{currency}:all")]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_currency_keyboard(i18n: Callable) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 USD", callback_data="alrt:cur:USD"),
                InlineKeyboardButton(text="💶 EUR", callback_data="alrt:cur:EUR"),
                InlineKeyboardButton(text="₽ RUB", callback_data="alrt:cur:RUB"),
            ]
        ]
    )


def alert_direction_keyboard(code: str, i18n: Callable) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=i18n("alert.above"), callback_data=f"alrt:dir:{code}:above")],
            [InlineKeyboardButton(text=i18n("alert.below"), callback_data=f"alrt:dir:{code}:below")],
        ]
    )


def alert_list_keyboard(alerts: list, i18n: Callable) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for a in alerts:
        arrow = "⬆️" if a.direction == "above" else "⬇️"
        label = f"❌ {a.code} {arrow} {float(a.threshold):,.0f}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"alrt:del:{a.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def chart_currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 USD", callback_data="chart:USD:7"),
                InlineKeyboardButton(text="💶 EUR", callback_data="chart:EUR:7"),
                InlineKeyboardButton(text="₽ RUB", callback_data="chart:RUB:7"),
            ]
        ]
    )


def chart_period_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="7 days", callback_data=f"chart:{code}:7"),
                InlineKeyboardButton(text="30 days", callback_data=f"chart:{code}:30"),
            ],
            [
                InlineKeyboardButton(text="💵 USD", callback_data="chart:USD:7"),
                InlineKeyboardButton(text="💶 EUR", callback_data="chart:EUR:7"),
                InlineKeyboardButton(text="₽ RUB", callback_data="chart:RUB:7"),
            ],
        ]
    )


def branch_location_keyboard(i18n: Callable) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Send Location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def map_provider_keyboard(rates: list, lat: float, lon: float) -> InlineKeyboardMarkup:
    """Build inline keyboard with map links for top banks across providers."""
    from urllib.parse import quote

    # Best bank name for the search query
    best_bank = rates[0].bank.name if rates else "bank"
    query_raw = f"{best_bank} bank"
    q = quote(query_raw)

    google_url = f"https://www.google.com/maps/search/{q}/@{lat},{lon},14z"
    yandex_url = f"https://yandex.com/maps/?text={q}&ll={lon},{lat}&z=14"
    twogis_url = f"https://2gis.uz/search/{q}?m={lon},{lat}/14"

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="🗺 Google Maps", url=google_url),
            InlineKeyboardButton(text="🟡 Yandex Maps", url=yandex_url),
        ],
        [
            InlineKeyboardButton(text="🟢 2GIS", url=twogis_url),
        ],
    ]

    # Per-bank rows (top 3) with Google Maps links
    for r in rates[:3]:
        name = r.bank.name
        bq = quote(f"{name} bank")
        rows.append([
            InlineKeyboardButton(
                text=f"📍 {name}",
                url=f"https://www.google.com/maps/search/{bq}/@{lat},{lon},14z",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Stats", callback_data="adm:stats")],
            [InlineKeyboardButton(text="🔄 Collectors", callback_data="adm:collectors")],
            [InlineKeyboardButton(text="⚠️ Stale Data", callback_data="adm:stale")],
            [InlineKeyboardButton(text="🔃 Run collectors now", callback_data="adm:run")],
        ]
    )


def autopost_schedule_keyboard(
    chat_id: int, current_schedule: str | None = None
) -> InlineKeyboardMarkup:
    """Schedule picker for channel/group auto-post."""
    options = [
        ("🌅 Morning", "morning"),
        ("🌆 Evening", "evening"),
        ("🔁 Twice a day", "twice"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for label, value in options:
        marker = " ✅" if current_schedule == value else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{label}{marker}",
                callback_data=f"autopost:sched:{chat_id}:{value}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="🌐 Language",
            callback_data=f"autopost:lang:{chat_id}",
        )
    ])
    if current_schedule:
        rows.append([
            InlineKeyboardButton(
                text="❌ Disable auto-post",
                callback_data=f"autopost:remove:{chat_id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def autopost_lang_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data=f"autopost:setlang:{chat_id}:uz_cy")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"autopost:setlang:{chat_id}:ru")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data=f"autopost:setlang:{chat_id}:en")],
        ]
    )
