"""All bot handlers: /start, /language, rates, subscription, digest schedule."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone, timedelta

TASHKENT_TZ = timezone(timedelta(hours=5))

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    CURRENCIES,
    currency_tabs,
    digest_schedule_keyboard,
    language_keyboard,
    main_keyboard,
)
from models import BankRate
from repos import BankRatesRepo, UserRepo

router = Router()

TOP_LIMIT = 5
PAGE_SIZE = 5

# ── Helpers ─────────────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _format_rates(
    currency: str,
    rates: list[BankRate],
    i18n,
    *,
    limit: int | None = None,
    page: int = 1,
    total_pages: int = 1,
) -> str:
    if not rates:
        return i18n("rates.no-rates")
    now = datetime.now(TASHKENT_TZ).strftime("%H:%M")
    parts = [
        f"💱 {i18n('rates.title')} — {currency}",
        f"🕐 {i18n('rates.last-updated', time=now)}",
        "",
    ]
    if total_pages > 1:
        parts.append(f"📄 {i18n('rates.page', current=page, total=total_pages)}")
    parts += [f"🏦 {i18n('rates.top-banks')}", ""]

    bank_h = i18n('rates.bank')
    buy_h = i18n('rates.buy')
    sell_h = i18n('rates.sell')
    header = f"{bank_h:<15} {buy_h:>8} {sell_h:>8} {'Δ':>6}"
    parts.append(f"`{header}`")
    parts.append("```")
    display = rates[:limit] if limit else rates
    for r in display:
        name = r.bank.name[:12] if len(r.bank.name) > 12 else r.bank.name
        buy_s = f"{float(r.buy):,.0f}"
        sell_s = f"{float(r.sell):,.0f}"
        delta = float(r.sell) - float(r.buy)
        parts.append(f"{name:<15} {buy_s:>8} {sell_s:>8} {delta:>+6.0f}")
    parts.append("```")
    parts += ["", f"ℹ️ {i18n('rates.disclaimer')}"]
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
    await message.answer(i18n("start.welcome"), reply_markup=kb)


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
    repo = BankRatesRepo(db_session)
    rates = await repo.latest_by_code("USD")
    text = _format_rates("USD", rates, i18n, limit=TOP_LIMIT)
    kb = currency_tabs("USD")
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


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
    key = "subscription.enabled" if is_sub else "subscription.disabled"
    await message.answer(i18n(key), reply_markup=kb)

    # If just subscribed, prompt for schedule
    if is_sub:
        await message.answer(
            i18n("schedule.prompt"), reply_markup=digest_schedule_keyboard(i18n)
        )


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
        text = _format_rates(currency, page_rates, i18n, page=page, total_pages=total)
        kb = currency_tabs(currency, page, total, show_all=True)
    else:
        text = _format_rates(currency, all_rates, i18n, limit=TOP_LIMIT)
        kb = currency_tabs(currency)

    # Dedup: skip if content unchanged
    msg_id = cb.message.message_id
    new_hash = _content_hash(text)
    cache_key = f"{cb.from_user.id}:{msg_id}"
    if kw.get("_hash_cache", {}).get(cache_key) == new_hash:
        await cb.answer()
        return

    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
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

    if schedule == "off":
        # Also unsubscribe
        await user_repo.soft_unsubscribe(cb.from_user.id)
        await cb.answer(i18n("subscription.disabled"))
    else:
        await cb.answer(i18n("schedule.saved", schedule=i18n(f"schedule.{schedule}")))

    if isinstance(cb.message, Message):
        try:
            await cb.message.delete()
        except Exception:
            pass


# ── Callback: noop (page indicator) ────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery, **kw):
    await cb.answer()
