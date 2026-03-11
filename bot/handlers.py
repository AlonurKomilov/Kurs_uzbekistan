"""All bot handlers: /start, /language, rates, subscription, digest schedule, converter."""

from __future__ import annotations

import hashlib
import html as _html
import math
from datetime import datetime, timezone, timedelta

TASHKENT_TZ = timezone(timedelta(hours=5))

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    Message,
    MessageEntity,
    ReactionTypeEmoji,
)
from aiogram.enums import ChatAction

from bot.keyboards import (
    CURRENCIES,
    converter_currency_keyboard,
    currency_tabs,
    digest_schedule_keyboard,
    language_keyboard,
    main_keyboard,
)
from models import BankRate
from repos import BankRatesRepo, UserRepo


class ConvertStates(StatesGroup):
    waiting_amount = State()

router = Router()

TOP_LIMIT = 5
PAGE_SIZE = 5

# ── Animated custom emoji IDs (from RestrictedEmoji / NewsEmoji packs) ─
# Premium users see animations; others see static fallback.
_EMOJI = {
    "rates":    "5471890899163709593",   # 💱 animated exchange
    "best_sell":"5373001317042101552",   # 📈 animated chart up
    "best_buy": "5361748661640372834",   # 📉 animated chart down
    "clock":    "5413704112220949842",   # ⏰ animated clock
    "bank":     "5264895611517300926",   # 🏦 animated bank
    "bell":     "5242628160297641831",   # 🔔 animated bell
    "check":    "5427009714745517609",   # ✅ animated checkmark
    "fire":     "5420315771991497307",   # 🔥 animated fire
    "party":    "5436040291507247633",   # 🎉 animated party
    "wave":     "5472055112702629499",   # 👋 animated wave
    "coin":     "5379600444098093058",   # 🪙 animated coin
    "globe":    "5447410659077661506",   # 🌐 animated globe
}

# Message effect IDs
_EFFECT = {
    "fire":     "5104841245755180586",
    "thumbs_up":"5107584321108051014",
    "heart":    "5159385139981059251",
    "party":    "5046509860389126442",
}


def _ce(emoji_key: str, fallback: str) -> tuple[str, list[MessageEntity]]:
    """Return (placeholder, entity) for an animated custom emoji."""
    eid = _EMOJI.get(emoji_key)
    if eid:
        return fallback, [MessageEntity(
            type="custom_emoji", offset=0, length=len(fallback),
            custom_emoji_id=eid,
        )]
    return fallback, []

# ── Helpers ─────────────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _format_rates(
    currency: str,
    rates: list[BankRate],
    i18n,
    *,
    all_rates: list[BankRate] | None = None,
    limit: int | None = None,
    page: int = 1,
    total_pages: int = 1,
) -> str:
    """Return formatted rate text (HTML with <pre> blocks)."""
    if not rates:
        return i18n("rates.no-rates")
    now = datetime.now(TASHKENT_TZ)
    month_name = i18n(f"month.{now.month}")
    date_str = f"{month_name} {now.day}, {now.strftime('%H:%M')}"

    display = rates[:limit] if limit else rates

    # Best rates from full dataset (stable across pages)
    source = all_rates if all_rates else rates
    best_sell = source[0] if source else None  # sorted by sell desc
    best_buy = max(source, key=lambda r: float(r.buy)) if source else None

    # Column headers (full words, from locale)
    col_bank = i18n("rates.bank")
    col_buy = i18n("rates.buy")
    col_sell = i18n("rates.sell")
    title_line = f"{i18n('rates.title')} — 1 {currency}"

    parts = [
        f"💱 {_html.escape(title_line)}",
        "",
        _html.escape(i18n("rates.best-legend")),
        "",
    ]

    # ── Highlights <pre> block ──
    hl_entries = []
    if best_sell:
        hl_entries.append(("↑", best_sell.bank.name, f"{float(best_sell.buy):,.0f}", f"{float(best_sell.sell):,.0f}"))
    if best_buy:
        hl_entries.append(("↓", best_buy.bank.name, f"{float(best_buy.buy):,.0f}", f"{float(best_buy.sell):,.0f}"))
    if hl_entries:
        max_n = max(len(e[1]) for e in hl_entries)
        name_w = max(max_n, len(col_bank) - 2)  # -2 for "↑ " prefix
        max_b = max(len(e[2]) for e in hl_entries)
        max_s = max(len(e[3]) for e in hl_entries)
        max_b = max(max_b, len(col_buy))
        max_s = max(max_s, len(col_sell))

        hdr = f"  {_html.escape(col_bank.ljust(name_w))}  {_html.escape(col_buy.rjust(max_b))}  {_html.escape(col_sell.rjust(max_s))}"
        hl_lines = [_html.escape(title_line), "", hdr]
        for arrow, name, buy_s, sell_s in hl_entries:
            n = _html.escape(name.ljust(name_w))
            hl_lines.append(f"{arrow} {n}  {buy_s:>{max_b}}  {sell_s:>{max_s}}")
        parts.append(f"<pre>{chr(10).join(hl_lines)}</pre>")
        parts.append("")

    # ── Section header ──
    parts.append(f"🏦 {_html.escape(i18n('rates.top-banks'))}")
    parts.append("")

    # ── Build aligned <pre> table with title + column header ──
    NAME_W = 14
    rows = []
    max_buy_w = 0
    max_sell_w = 0
    for r in display:
        name = r.bank.name[:NAME_W]
        buy_s = f"{float(r.buy):,.0f}"
        sell_s = f"{float(r.sell):,.0f}"
        max_buy_w = max(max_buy_w, len(buy_s))
        max_sell_w = max(max_sell_w, len(sell_s))
        rows.append((name, buy_s, sell_s))

    max_buy_w = max(max_buy_w, len(col_buy))
    max_sell_w = max(max_sell_w, len(col_sell))

    # Title row inside table
    tbl_title = _html.escape(title_line)
    hdr = f"{_html.escape(col_bank.ljust(NAME_W))}  {_html.escape(col_buy.rjust(max_buy_w))}  {_html.escape(col_sell.rjust(max_sell_w))}"
    lines = [tbl_title, "", hdr]
    for name, buy_s, sell_s in rows:
        n = _html.escape(name.ljust(NAME_W))
        lines.append(f"{n}  {buy_s:>{max_buy_w}}  {sell_s:>{max_sell_w}}")

    parts.append(f"<pre>{chr(10).join(lines)}</pre>")

    # ── Page info (below table) ──
    if total_pages > 1:
        parts.append("")
        parts.append(f"📄 {_html.escape(i18n('rates.page', current=page, total=total_pages))}")

    parts += [
        "",
        f"ℹ️ {_html.escape(i18n('rates.disclaimer'))}",
        "",
        f"{_html.escape(i18n('rates.last-updated', time=date_str))}",
    ]
    return "\n".join(parts)


def _paginate(items: list, page: int, size: int = PAGE_SIZE):
    total = max(1, math.ceil(len(items) / size))
    page = max(1, min(page, total))
    start = (page - 1) * size
    return items[start : start + size], page, total


# ── /start ──────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, i18n, user_repo: UserRepo, **kw):
    if not message.from_user:
        return
    user = await user_repo.get_or_create(message.from_user.id)
    kb = main_keyboard(i18n, bool(user.subscribed))
    # Single emoji → fullscreen animation on mobile
    try:
        await message.answer("👋")
    except Exception:
        pass
    # Welcome text with animated 💱 custom emoji
    welcome = i18n("start.welcome")
    eid = _EMOJI.get("rates")
    if eid:
        # Prepend animated 💱 before the text
        full = f"💱 {welcome}"
        entities = [MessageEntity(
            type="custom_emoji", offset=0, length=2,
            custom_emoji_id=eid,
        )]
        await message.answer(full, reply_markup=kb, entities=entities)
    else:
        await message.answer(welcome, reply_markup=kb)


# ── /language ───────────────────────────────────────────────────────────

@router.message(Command("language"))
async def cmd_language(message: Message, i18n, **kw):
    await message.answer(i18n("lang.select"), reply_markup=language_keyboard(i18n))


@router.callback_query(lambda c: c.data and c.data.startswith("lang:"))
async def cb_language(cb: CallbackQuery, i18n, user_repo: UserRepo, **kw):
    if not cb.data or not cb.from_user:
        return
    lang = cb.data.split(":")[1]

    await user_repo.update_language(cb.from_user.id, lang)

    # rebuild i18n for new lang
    from bot.middlewares import I18nMiddleware
    _i18n_mw = I18nMiddleware()
    new_i18n = lambda key, **kwa: _i18n_mw.get_text(lang, key, **kwa)

    user = await user_repo.get_or_create(cb.from_user.id)
    kb = main_keyboard(new_i18n, bool(user.subscribed))
    await cb.answer(new_i18n("lang.saved"))

    if cb.message and isinstance(cb.message, Message):
        try:
            await cb.message.delete()
        except Exception:
            pass
    if cb.message:
        await cb.message.answer(new_i18n("start.welcome"), reply_markup=kb)


# ── Button: Current Rates (matched via i18n key) ───────────────────────

@router.message(
    lambda m: m.text
    and any(
        phrase in m.text
        for phrase in [
            "Current Rates",
            "Ҳозирги курс",
            "Текущий курс",
        ]
    )
)
async def btn_current_rates(message: Message, i18n, db_session, **kw):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    repo = BankRatesRepo(db_session)
    rates = await repo.latest_by_code("USD")
    text = _format_rates("USD", rates, i18n, limit=TOP_LIMIT)
    kb = currency_tabs("USD", i18n=i18n)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    try:
        await sent.react([ReactionTypeEmoji(emoji="💱")])
    except Exception:
        pass


# ── Button: Subscribe / Unsubscribe ────────────────────────────────────

@router.message(
    lambda m: m.text
    and any(
        phrase in m.text
        for phrase in [
            "Subscribe",
            "Unsubscribe",
            "Обуна",
            "беков",
            "Подписаться",
            "Отписаться",
        ]
    )
)
async def btn_subscription(message: Message, i18n, user_repo: UserRepo, **kw):
    if not message.from_user:
        return
    user = await user_repo.toggle_subscription(message.from_user.id)
    if not user:
        await message.answer(i18n("subscription.error"))
        return
    is_sub = bool(user.subscribed)
    kb = main_keyboard(i18n, is_sub)

    if is_sub:
        # Show schedule picker first — confirmation comes after selection
        await message.answer(
            i18n("schedule.prompt"), reply_markup=digest_schedule_keyboard(i18n)
        )
    else:
        await message.answer(i18n("subscription.disabled"), reply_markup=kb)


# ── Button: Language ────────────────────────────────────────────────────

@router.message(
    lambda m: m.text and any(w in m.text for w in ("Language", "Тил", "Язык"))
)
async def btn_language(message: Message, i18n, **kw):
    await message.answer(i18n("lang.select"), reply_markup=language_keyboard(i18n))


# ── Callback: currency tabs + pagination ────────────────────────────────

@router.callback_query(F.data.startswith("cr:"))
async def cb_currency_rates(cb: CallbackQuery, i18n, db_session, **kw):
    if not cb.data or not cb.message or not cb.from_user:
        return
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer()
        return

    currency = parts[1]
    mode_raw = parts[2]
    if currency not in CURRENCIES:
        await cb.answer()
        return

    show_all = False
    page = 1
    if mode_raw == "top":
        show_all = False
    elif mode_raw == "all":
        show_all = True
    elif mode_raw.startswith("p"):
        show_all = True
        try:
            page = max(1, int(mode_raw[1:]))
        except ValueError:
            await cb.answer()
            return

    repo = BankRatesRepo(db_session)
    all_rates = await repo.latest_by_code(currency)

    if show_all:
        page_rates, page, total = _paginate(all_rates, page)
        text = _format_rates(currency, page_rates, i18n, all_rates=all_rates, page=page, total_pages=total)
        kb = currency_tabs(currency, page, total, show_all=True, i18n=i18n)
    else:
        text = _format_rates(currency, all_rates, i18n, limit=TOP_LIMIT)
        kb = currency_tabs(currency, i18n=i18n)

    # Dedup: skip if content unchanged
    msg_id = cb.message.message_id
    new_hash = _content_hash(text)
    cache_key = f"{cb.from_user.id}:{msg_id}"
    if kw.get("_hash_cache", {}).get(cache_key) == new_hash:
        await cb.answer()
        return

    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    await cb.answer()


# ── Callback: digest schedule ───────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("sched:"))
async def cb_schedule(cb: CallbackQuery, i18n, user_repo: UserRepo, **kw):
    if not cb.data or not cb.from_user:
        return
    schedule = cb.data.split(":")[1]
    if schedule not in ("morning", "evening", "twice", "off"):
        await cb.answer()
        return

    await user_repo.set_digest_schedule(cb.from_user.id, schedule)

    if isinstance(cb.message, Message):
        try:
            await cb.message.delete()
        except Exception:
            pass

    if schedule == "off":
        # Also unsubscribe
        await user_repo.soft_unsubscribe(cb.from_user.id)
        user = await user_repo.get_or_create(cb.from_user.id)
        kb = main_keyboard(i18n, bool(user.subscribed))
        await cb.message.answer(i18n("subscription.disabled"), reply_markup=kb)
    else:
        user = await user_repo.get_or_create(cb.from_user.id)
        kb = main_keyboard(i18n, bool(user.subscribed))
        await cb.message.answer(
            i18n("subscription.enabled"),
            reply_markup=kb,
            message_effect_id=_EFFECT["thumbs_up"],
        )
    await cb.answer()


# ── Callback: noop (page indicator) ────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery, **kw):
    await cb.answer()


# ── Button: Converter ───────────────────────────────────────────────────

@router.message(
    lambda m: m.text
    and any(
        phrase in m.text
        for phrase in ["Converter", "Конвертер"]
    )
)
async def btn_converter(message: Message, i18n, state: FSMContext, **kw):
    await state.clear()
    # Animated 🪙 custom emoji on converter prompt
    prompt = i18n("converter.prompt")
    eid = _EMOJI.get("coin")
    if eid:
        full = f"🪙 {prompt}"
        entities = [MessageEntity(
            type="custom_emoji", offset=0, length=2,
            custom_emoji_id=eid,
        )]
        await message.answer(
            full, reply_markup=converter_currency_keyboard(i18n), entities=entities
        )
    else:
        await message.answer(
            prompt, reply_markup=converter_currency_keyboard(i18n)
        )


@router.callback_query(F.data.startswith("conv:"))
async def cb_converter_currency(cb: CallbackQuery, i18n, state: FSMContext, **kw):
    if not cb.data or not cb.from_user:
        return
    currency = cb.data.split(":")[1]
    if currency not in CURRENCIES:
        await cb.answer()
        return

    await state.set_state(ConvertStates.waiting_amount)
    await state.update_data(conv_currency=currency)

    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(i18n("converter.enter-amount", currency=currency))
        except Exception:
            pass
    await cb.answer()


@router.message(ConvertStates.waiting_amount)
async def msg_converter_amount(message: Message, i18n, db_session, state: FSMContext, user_repo: UserRepo, **kw):
    data = await state.get_data()
    currency = data.get("conv_currency", "USD")
    await state.clear()

    if not message.text:
        return

    raw = message.text.replace(",", ".").replace(" ", "")
    try:
        amount = float(raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(i18n("converter.error"))
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    repo = BankRatesRepo(db_session)
    cbu_rate = await repo.get_cbu_rate(currency)
    if not cbu_rate:
        await message.answer(i18n("rates.no-rates"))
        return

    rate_val = float(cbu_rate.buy)
    result = amount * rate_val
    await message.answer(
        i18n(
            "converter.result",
            amount=f"{amount:,.2f}",
            currency=currency,
            result=f"{result:,.0f}",
            rate=f"{rate_val:,.2f}",
        ),
    )


# ── Catch-all: unknown text ────────────────────────────────────────────
# Must be registered LAST so it doesn't intercept button presses.

@router.message()
async def msg_unknown(message: Message, i18n, user_repo: UserRepo, **kw):
    if not message.from_user:
        return
    user = await user_repo.get_or_create(message.from_user.id)
    kb = main_keyboard(i18n, bool(user.subscribed))
    await message.answer(i18n("unknown.use-buttons"), reply_markup=kb)
