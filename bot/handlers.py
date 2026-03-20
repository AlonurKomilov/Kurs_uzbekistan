"""All bot handlers: /start, /language, rates, subscription, digest schedule, converter."""

from __future__ import annotations

import hashlib
import html as _html
import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

TASHKENT_TZ = timezone(timedelta(hours=5))

logger = logging.getLogger(__name__)

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    MessageEntity,
    ReactionTypeEmoji,
)
from aiogram.enums import ChatAction

from bot.keyboards import (
    CURRENCIES,
    admin_keyboard,
    alert_currency_keyboard,
    alert_direction_keyboard,
    alert_list_keyboard,
    autopost_lang_keyboard,
    autopost_schedule_keyboard,
    branch_location_keyboard,
    chart_currency_keyboard,
    chart_period_keyboard,
    converter_currency_keyboard,
    currency_tabs,
    digest_schedule_keyboard,
    language_keyboard,
    main_keyboard,
)
from models import BankRate
from repos import AlertRepo, BankRatesRepo, ChannelSubRepo, UserRepo, StatsRepo
import cache
from config import settings


class ConvertStates(StatesGroup):
    waiting_amount = State()


class AlertStates(StatesGroup):
    waiting_threshold = State()

router = Router()

TOP_LIMIT = 5
PAGE_SIZE = 5

# ── Rate limiter (per-user, in-memory) ──────────────────────────────────

_rate_limits: dict[str, dict[int, float]] = defaultdict(dict)


def _is_rate_limited(user_id: int, action: str, cooldown: float = 10.0) -> bool:
    """Return True if user_id should be throttled for action."""
    now = time.monotonic()
    last = _rate_limits[action].get(user_id, 0.0)
    if now - last < cooldown:
        return True
    _rate_limits[action][user_id] = now
    return False


# ── Safe Telegram message helpers ────────────────────────────────────────

async def _safe_delete(msg) -> None:
    if isinstance(msg, Message):
        try:
            await msg.delete()
        except Exception as e:
            logger.debug("Could not delete message: %s", e)


async def _safe_edit(msg, text: str, **kwargs) -> None:
    if isinstance(msg, Message):
        try:
            await msg.edit_text(text, **kwargs)
        except Exception as e:
            logger.debug("Could not edit message: %s", e)


async def _safe_edit_markup(msg, **kwargs) -> None:
    if isinstance(msg, Message):
        try:
            await msg.edit_reply_markup(**kwargs)
        except Exception as e:
            logger.debug("Could not edit reply markup: %s", e)


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
    prev_rates: dict[int, BankRate] | None = None,
    limit: int | None = None,
    page: int = 1,
    total_pages: int = 1,
) -> str:
    """Return formatted rate text (HTML with <pre> blocks)."""
    if not rates:
        return i18n("rates.no-rates")
    # Use the latest fetched_at from rates as the "last updated" time
    latest_fetched = max(r.fetched_at for r in rates)
    if latest_fetched.tzinfo is None:
        latest_fetched = latest_fetched.replace(tzinfo=timezone.utc)
    fetched_local = latest_fetched.astimezone(TASHKENT_TZ)
    month_name = i18n(f"month.{fetched_local.month}")
    date_str = f"{month_name} {fetched_local.day}, {fetched_local.strftime('%H:%M')}"

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
    prev = prev_rates or {}
    rows = []
    max_buy_w = 0
    max_sell_w = 0
    for r in display:
        name = r.bank.name[:NAME_W]
        buy_s = f"{float(r.buy):,.0f}"
        sell_s = f"{float(r.sell):,.0f}"
        # Change indicator based on sell price vs previous collection
        old = prev.get(r.bank_id)
        if old is None:
            arrow = " "
        elif float(r.sell) > float(old.sell):
            arrow = "▲"
        elif float(r.sell) < float(old.sell):
            arrow = "▼"
        else:
            arrow = " "
        max_buy_w = max(max_buy_w, len(buy_s))
        max_sell_w = max(max_sell_w, len(sell_s))
        rows.append((name, buy_s, sell_s, arrow))

    max_buy_w = max(max_buy_w, len(col_buy))
    max_sell_w = max(max_sell_w, len(col_sell))

    # Title row inside table
    tbl_title = _html.escape(title_line)
    hdr = f"{_html.escape(col_bank.ljust(NAME_W))}  {_html.escape(col_buy.rjust(max_buy_w))}  {_html.escape(col_sell.rjust(max_sell_w))}"
    lines = [tbl_title, "", hdr]
    for name, buy_s, sell_s, arrow in rows:
        n = _html.escape(name.ljust(NAME_W))
        lines.append(f"{n}  {buy_s:>{max_buy_w}}  {sell_s:>{max_sell_w}} {arrow}")

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


def _inline_text(currency: str, rates: list[BankRate], i18n) -> str:
    """Compact HTML text for inline query results."""
    if not rates:
        return i18n("rates.no-rates")
    latest_fetched = max(r.fetched_at for r in rates)
    if latest_fetched.tzinfo is None:
        latest_fetched = latest_fetched.replace(tzinfo=timezone.utc)
    fetched_local = latest_fetched.astimezone(TASHKENT_TZ)
    month_name = i18n(f"month.{fetched_local.month}")
    date_str = f"{month_name} {fetched_local.day}, {fetched_local.strftime('%H:%M')}"

    col_bank = i18n("rates.bank")
    col_buy = i18n("rates.buy")
    col_sell = i18n("rates.sell")
    title_line = f"{i18n('rates.title')} — 1 {currency}"

    NAME_W = 14
    rows = []
    max_buy_w = max_sell_w = 0
    for r in rates[:TOP_LIMIT]:
        name = r.bank.name[:NAME_W]
        buy_s = f"{float(r.buy):,.0f}"
        sell_s = f"{float(r.sell):,.0f}"
        max_buy_w = max(max_buy_w, len(buy_s))
        max_sell_w = max(max_sell_w, len(sell_s))
        rows.append((name, buy_s, sell_s))
    max_buy_w = max(max_buy_w, len(col_buy))
    max_sell_w = max(max_sell_w, len(col_sell))

    hdr = f"{_html.escape(col_bank.ljust(NAME_W))}  {_html.escape(col_buy.rjust(max_buy_w))}  {_html.escape(col_sell.rjust(max_sell_w))}"
    lines = [_html.escape(title_line), "", hdr]
    for name, buy_s, sell_s in rows:
        n = _html.escape(name.ljust(NAME_W))
        lines.append(f"{n}  {buy_s:>{max_buy_w}}  {sell_s:>{max_sell_w}}")

    parts = [
        f"\U0001f4b1 {_html.escape(title_line)}",
        "",
        f"<pre>{chr(10).join(lines)}</pre>",
        "",
        f"{_html.escape(i18n('rates.last-updated', time=date_str))}",
    ]
    return "\n".join(parts)


# ── /start ──────────────────────────────────────────────────────────────

# ── Inline mode ───────────────────────────────────────────────────────────────

@router.inline_query()
async def inline_rates(query: InlineQuery, i18n, db_session, **kw):
    q = (query.query or "").strip().upper()
    codes = [q] if q in CURRENCIES else list(CURRENCIES)

    repo = BankRatesRepo(db_session)
    results = []
    for code in codes:
        rates = cache.get(f"rates:{code}")
        if rates is None:
            rates = await repo.latest_by_code(code)
            cache.put(f"rates:{code}", rates)
        if not rates:
            continue
        best_sell = rates[0]
        text = _inline_text(code, rates, i18n)
        results.append(
            InlineQueryResultArticle(
                id=f"rates_{code}",
                title=f"{code} — {float(best_sell.sell):,.0f}",
                description=f"Top {TOP_LIMIT} banks",
                input_message_content=InputTextMessageContent(
                    message_text=text,
                    parse_mode="HTML",
                ),
            )
        )
    await query.answer(results, cache_time=60, is_personal=True)

@router.message(Command("start"))
async def cmd_start(message: Message, i18n, user_repo: UserRepo, **kw):
    if not message.from_user:
        return
    user = await user_repo.get_or_create(message.from_user.id)
    kb = main_keyboard(i18n, bool(user.subscribed))
    # Single emoji → fullscreen animation on mobile
    try:
        await message.answer("👋")
    except Exception as e:
        logger.debug("cmd_start emoji send failed: %s", e)
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

    await _safe_delete(cb.message)
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
    rates = cache.get("rates:USD")
    if rates is None:
        rates = await repo.latest_by_code("USD")
        cache.put("rates:USD", rates)
    prev = cache.get("prev:USD")
    if prev is None:
        prev = await repo.previous_by_code("USD")
        cache.put("prev:USD", prev)
    text = _format_rates("USD", rates, i18n, prev_rates=prev, limit=TOP_LIMIT)
    kb = currency_tabs("USD", i18n=i18n)
    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    try:
        await sent.react([ReactionTypeEmoji(emoji="💱")])
    except Exception as e:
        logger.debug("React failed: %s", e)


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
    all_rates = cache.get(f"rates:{currency}")
    if all_rates is None:
        all_rates = await repo.latest_by_code(currency)
        cache.put(f"rates:{currency}", all_rates)
    prev = cache.get(f"prev:{currency}")
    if prev is None:
        prev = await repo.previous_by_code(currency)
        cache.put(f"prev:{currency}", prev)

    if show_all:
        page_rates, page, total = _paginate(all_rates, page)
        text = _format_rates(currency, page_rates, i18n, all_rates=all_rates, prev_rates=prev, page=page, total_pages=total)
        kb = currency_tabs(currency, page, total, show_all=True, i18n=i18n)
    else:
        text = _format_rates(currency, all_rates, i18n, prev_rates=prev, limit=TOP_LIMIT)
        kb = currency_tabs(currency, i18n=i18n)

    # Dedup: skip if content unchanged
    msg_id = cb.message.message_id
    new_hash = _content_hash(text)
    cache_key = f"{cb.from_user.id}:{msg_id}"
    if kw.get("_hash_cache", {}).get(cache_key) == new_hash:
        await cb.answer()
        return

    await _safe_edit(cb.message, text, reply_markup=kb, parse_mode="HTML")
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

    await _safe_delete(cb.message)

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


# ── Button: Alerts ─────────────────────────────────────────────────────

@router.message(
    lambda m: m.text
    and any(
        phrase in m.text
        for phrase in ["Alerts", "Оповещения", "Огоҳлантириш"]
    )
)
async def btn_alerts(message: Message, i18n, db_session, **kw):
    if not message.from_user:
        return
    from repos import AlertRepo
    from bot.keyboards import alert_list_keyboard, alert_currency_keyboard
    alert_repo = AlertRepo(db_session)
    alerts = await alert_repo.list_active(message.from_user.id)
    if alerts:
        await message.answer(
            i18n("alert.list-title"),
            reply_markup=alert_list_keyboard(alerts, i18n),
        )
    await message.answer(
        i18n("alert.set-currency"),
        reply_markup=alert_currency_keyboard(i18n),
    )


# ── Button: Chart ───────────────────────────────────────────────────────

@router.message(
    lambda m: m.text
    and any(
        phrase in m.text
        for phrase in ["Chart", "График", "Диаграмма"]
    )
)
async def btn_chart(message: Message, i18n, **kw):
    from bot.keyboards import chart_currency_keyboard
    await message.answer(
        i18n("chart.title", code="...", days=7),
        reply_markup=chart_currency_keyboard(),
    )


# ── Button: Nearest Branch ──────────────────────────────────────────────

@router.message(
    lambda m: m.text
    and any(
        phrase in m.text
        for phrase in ["Nearest Branch", "Ближайший банк", "Яқин банк"]
    )
)
async def btn_branch(message: Message, i18n, **kw):
    from bot.keyboards import branch_location_keyboard
    await message.answer(
        i18n("branch.prompt"),
        reply_markup=branch_location_keyboard(i18n),
    )


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

    await _safe_edit(cb.message, i18n("converter.enter-amount", currency=currency))
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


# ── /alert — set + list rate alerts ────────────────────────────────────

ALERT_LIMIT = 5

@router.message(Command("alert"))
async def cmd_alert(message: Message, i18n, db_session, **kw):
    if not message.from_user:
        return
    repo = AlertRepo(db_session)
    alerts = await repo.list_active(message.from_user.id)
    if alerts:
        lines = [i18n("alert.list-title"), ""]
        for a in alerts:
            arrow = "⬆" if a.direction == "above" else "⬇"
            lines.append(f"  • {a.code} sell {arrow} {float(a.threshold):,.0f}")
        text = "\n".join(lines)
        await message.answer(text, reply_markup=alert_list_keyboard(alerts, i18n))
    await message.answer(i18n("alert.set-currency"), reply_markup=alert_currency_keyboard(i18n))


@router.callback_query(F.data.startswith("alrt:cur:"))
async def cb_alert_currency(cb: CallbackQuery, i18n, **kw):
    if not cb.data or not cb.from_user:
        return
    code = cb.data.split(":")[2]
    if code not in CURRENCIES:
        await cb.answer()
        return
    await _safe_edit(
        cb.message,
        i18n("alert.set-direction"),
        reply_markup=alert_direction_keyboard(code, i18n),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("alrt:dir:"))
async def cb_alert_direction(cb: CallbackQuery, i18n, db_session, state: FSMContext, **kw):
    if not cb.data or not cb.from_user:
        return
    parts = cb.data.split(":")
    if len(parts) < 4:
        await cb.answer()
        return
    code, direction = parts[2], parts[3]
    if code not in CURRENCIES or direction not in ("above", "below"):
        await cb.answer()
        return

    repo = AlertRepo(db_session)
    existing = await repo.list_active(cb.from_user.id)
    if len(existing) >= ALERT_LIMIT:
        await cb.answer(i18n("alert.limit"), show_alert=True)
        return

    await state.set_state(AlertStates.waiting_threshold)
    await state.update_data(alert_code=code, alert_direction=direction)

    # Fetch current best sell rate to show as reference
    rates_data = cache.get(f"rates:{code}")
    if rates_data is None:
        rates_repo = BankRatesRepo(db_session)
        rates_data = await rates_repo.latest_by_code(code)
        cache.put(f"rates:{code}", rates_data)
    current_sell = f"{float(rates_data[0].sell):,.0f}" if rates_data else "—"

    await _safe_edit(
        cb.message,
        i18n("alert.enter-threshold", code=code, rate=current_sell),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AlertStates.waiting_threshold)
async def msg_alert_threshold(message: Message, i18n, db_session, state: FSMContext, **kw):
    data = await state.get_data()
    code = data.get("alert_code", "USD")
    direction = data.get("alert_direction", "above")
    await state.clear()

    if not message.text or not message.from_user:
        return

    raw = message.text.replace(",", ".").replace(" ", "")
    try:
        threshold = float(raw)
        if threshold <= 0:
            raise ValueError
    except ValueError:
        await message.answer(i18n("alert.invalid-number"))
        return

    repo = AlertRepo(db_session)
    await repo.create(message.from_user.id, code, direction, threshold)
    arrow = "⬆" if direction == "above" else "⬇"
    await message.answer(
        i18n("alert.created", code=code, direction=arrow, threshold=f"{threshold:,.0f}")
    )


@router.callback_query(F.data.startswith("alrt:del:"))
async def cb_alert_delete(cb: CallbackQuery, i18n, db_session, **kw):
    if not cb.data or not cb.from_user:
        return
    try:
        alert_id = int(cb.data.split(":")[2])
    except (ValueError, IndexError):
        await cb.answer()
        return

    repo = AlertRepo(db_session)
    await repo.delete_by_id(alert_id, cb.from_user.id)
    await cb.answer(i18n("alert.deleted"))
    await _safe_delete(cb.message)


# ── /chart — historical rate chart ─────────────────────────────────────

@router.message(Command("chart"))
async def cmd_chart(message: Message, i18n, **kw):
    await message.answer(
        i18n("chart.title", code="...", days=7),
        reply_markup=chart_currency_keyboard(),
    )


@router.callback_query(F.data.startswith("chart:"))
async def cb_chart(cb: CallbackQuery, i18n, db_session, **kw):
    if not cb.data or not cb.from_user or not cb.message:
        return

    # Rate limit: 1 chart per user per 15 seconds
    if _is_rate_limited(cb.from_user.id, "chart", cooldown=15.0):
        await cb.answer("⏳ Please wait before requesting another chart.", show_alert=True)
        return

    parts = cb.data.split(":")
    code = parts[1] if len(parts) > 1 else "USD"
    try:
        days = int(parts[2]) if len(parts) > 2 else 7
    except ValueError:
        days = 7
    if code not in CURRENCIES or days not in (7, 30):
        await cb.answer()
        return

    await cb.answer()
    await cb.message.bot.send_chat_action(cb.message.chat.id, ChatAction.UPLOAD_PHOTO)

    repo = AlertRepo(db_session)
    data = await repo.history_for_chart(code, days=days)
    if not data:
        await _safe_edit(cb.message, i18n("chart.no-data", code=code))
        return

    import asyncio
    import io
    import functools

    def _make_chart(data, code, days, i18n_title):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.ticker import FuncFormatter
        import numpy as np

        dates = [row[0] for row in data]
        sells = np.array([row[1] for row in data])
        buys = np.array([row[2] for row in data])

        # Dark professional theme
        bg_color = "#1a1a2e"
        card_color = "#16213e"
        text_color = "#e0e0e0"
        grid_color = "#2a2a4a"
        sell_color = "#ff6b6b"
        buy_color = "#51cf66"
        accent = "#4dabf7"

        fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=bg_color)
        ax.set_facecolor(card_color)

        # Sell line with glow effect
        ax.plot(dates, sells, color=sell_color, linewidth=1, alpha=0.3)
        ax.plot(dates, sells, "o-", color=sell_color, label="Best Sell",
                linewidth=2.5, markersize=5, markerfacecolor="white",
                markeredgecolor=sell_color, markeredgewidth=1.5, zorder=5)

        # Buy line with glow effect
        ax.plot(dates, buys, color=buy_color, linewidth=1, alpha=0.3)
        ax.plot(dates, buys, "o-", color=buy_color, label="Best Buy",
                linewidth=2.5, markersize=5, markerfacecolor="white",
                markeredgecolor=buy_color, markeredgewidth=1.5, zorder=5)

        # Gradient fill between
        ax.fill_between(dates, buys, sells, alpha=0.15, color=accent)

        # Expand Y range to make room for annotations
        y_range = max(sells) - min(buys)
        pad = max(y_range * 0.15, 20)
        ax.set_ylim(min(buys) - pad, max(sells) + pad)

        # Annotate latest values (right side, stacked vertically with spacing)
        if len(dates) >= 1:
            sell_val = sells[-1]
            buy_val = buys[-1]
            spread = sell_val - buy_val

            # Place sell label above, buy label below, spread in middle
            # Calculate if values are too close
            gap = sell_val - buy_val
            if gap < y_range * 0.08:
                sell_offset = 18
                buy_offset = -22
            else:
                sell_offset = 12
                buy_offset = -16

            ax.annotate(f"{sell_val:,.0f}",
                        xy=(dates[-1], sell_val),
                        xytext=(-50, sell_offset), textcoords="offset points",
                        fontsize=10, fontweight="bold", color=sell_color,
                        ha="center",
                        bbox=dict(boxstyle="round,pad=0.3", facecolor=bg_color,
                                  edgecolor=sell_color, alpha=0.9),
                        zorder=10)
            ax.annotate(f"{buy_val:,.0f}",
                        xy=(dates[-1], buy_val),
                        xytext=(-50, buy_offset), textcoords="offset points",
                        fontsize=10, fontweight="bold", color=buy_color,
                        ha="center",
                        bbox=dict(boxstyle="round,pad=0.3", facecolor=bg_color,
                                  edgecolor=buy_color, alpha=0.9),
                        zorder=10)

            # Spread as subtitle text below title instead of on chart
            ax.text(0.98, 0.95, f"Spread: {spread:,.0f}",
                    transform=ax.transAxes, fontsize=10, color=accent,
                    ha="right", va="top",
                    bbox=dict(boxstyle="round,pad=0.4", facecolor=bg_color,
                              edgecolor=accent, alpha=0.8))

        # Min/Max markers — only if not at the last point (to avoid overlap)
        if len(sells) > 2:
            max_idx = int(np.argmax(sells))
            min_idx = int(np.argmin(buys))
            last_idx = len(sells) - 1

            if max_idx != last_idx:
                ax.annotate(f"\u25b2 {sells[max_idx]:,.0f}",
                            xy=(dates[max_idx], sells[max_idx]),
                            xytext=(0, 14), textcoords="offset points",
                            fontsize=8, color=sell_color, ha="center",
                            fontweight="bold", zorder=10)
            if min_idx != last_idx:
                ax.annotate(f"\u25bc {buys[min_idx]:,.0f}",
                            xy=(dates[min_idx], buys[min_idx]),
                            xytext=(0, -16), textcoords="offset points",
                            fontsize=8, color=buy_color, ha="center",
                            fontweight="bold", zorder=10)

        # Title + styling
        ax.set_title(i18n_title, fontsize=16, fontweight="bold", color=text_color, pad=15)
        ax.set_ylabel("UZS", fontsize=12, color=text_color, fontweight="bold")

        # Format Y axis with commas
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}"))

        # Grid
        ax.grid(True, alpha=0.3, color=grid_color, linestyle="--")
        ax.tick_params(colors=text_color, labelsize=10)

        # X axis date format
        if days <= 7:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %m/%d"))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        fig.autofmt_xdate(rotation=30)

        # Legend — bottom right to avoid data area
        ax.legend(loc="lower right", fontsize=10, framealpha=0.8,
                  facecolor=card_color, edgecolor=grid_color, labelcolor=text_color)

        # Spines
        for spine in ax.spines.values():
            spine.set_color(grid_color)

        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=bg_color, edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf

    from aiogram.types import BufferedInputFile
    title = i18n("chart.title", code=code, days=days)
    loop = asyncio.get_event_loop()
    try:
        buf = await asyncio.wait_for(
            loop.run_in_executor(None, functools.partial(_make_chart, data, code, days, title)),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Chart generation timed out for %s/%dd", code, days)
        await _safe_edit(cb.message, "Chart generation timed out. Please try again.")
        return
    photo = BufferedInputFile(buf.read(), filename=f"{code}_chart.png")

    await _safe_delete(cb.message)
    await cb.message.answer_photo(photo, caption=title, reply_markup=chart_period_keyboard(code))


# ── /branch — nearest branch finder ────────────────────────────────────

@router.message(Command("branch"))
async def cmd_branch(message: Message, i18n, user_repo: UserRepo, **kw):
    if not message.from_user:
        return
    await message.answer(
        i18n("branch.prompt"),
        reply_markup=branch_location_keyboard(i18n),
    )


@router.message(F.location)
async def msg_location(message: Message, i18n, db_session, user_repo: UserRepo, **kw):
    if not message.from_user or not message.location:
        return

    lat = message.location.latitude
    lon = message.location.longitude

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    repo = BankRatesRepo(db_session)
    rates = cache.get("rates:USD")
    if rates is None:
        rates = await repo.latest_by_code("USD")
        cache.put("rates:USD", rates)

    if not rates:
        await message.answer(i18n("rates.no-rates"))
        return

    from urllib.parse import quote
    lines = [f"\U0001f3e6 {i18n('branch.header', code='USD')}", ""]
    for i, r in enumerate(rates[:5], 1):
        bank_name = r.bank.name
        sell_s = f"{float(r.sell):,.0f}"
        buy_s = f"{float(r.buy):,.0f}"
        lines.append(
            f"{i}. <b>{_html.escape(bank_name)}</b>\n"
            f"   \U0001f4b0 {buy_s} / {sell_s}"
        )
        lines.append("")
    lines.append(i18n("branch.choose-map"))
    text = "\n".join(lines)

    from bot.keyboards import map_provider_keyboard
    kb = map_provider_keyboard(rates[:5], lat, lon)

    await message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

    # Restore main keyboard
    user = await user_repo.get_or_create(message.from_user.id)
    mkb = main_keyboard(i18n, bool(user.subscribed))
    await message.answer("\u2b07\ufe0f", reply_markup=mkb)


# ── Admin: /admin ───────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message, **kw):
    if not message.from_user or not _is_admin(message.from_user.id):
        if message.from_user:
            logger.warning("Unauthorized /admin attempt by user %d", message.from_user.id)
        return
    await message.answer("🔧 Admin panel", reply_markup=admin_keyboard())


@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(cb: CallbackQuery, db_session, **kw):
    if not cb.from_user or not _is_admin(cb.from_user.id):
        await cb.answer()
        return

    import os
    import collector_stats

    stats_repo = StatsRepo(db_session)
    rates_repo = BankRatesRepo(db_session)

    users = await stats_repo.count_users()
    subs = await stats_repo.count_subscribers()
    sched = await stats_repo.subscribers_by_schedule()
    new_7d = await stats_repo.new_users(7)
    total_rates = await rates_repo.count_rates()
    total_banks = await rates_repo.count_banks()
    last_fetch = await rates_repo.last_collection_time()

    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "kurs_uz.db")
    try:
        db_size_kb = os.path.getsize(db_path) / 1024
        db_size = f"{db_size_kb:.0f} KB" if db_size_kb < 1024 else f"{db_size_kb / 1024:.1f} MB"
    except OSError:
        db_size = "N/A"

    uptime = collector_stats.uptime_seconds()
    h, rem = divmod(int(uptime), 3600)
    m, s = divmod(rem, 60)

    sched_lines = "\n".join(f"  {k}: {v}" for k, v in sched.items()) or "  none"
    last_str = last_fetch.strftime("%Y-%m-%d %H:%M UTC") if last_fetch else "never"

    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Users: {users}\n"
        f"  new (7d): +{new_7d}\n"
        f"🔔 Subscribers: {subs}\n"
        f"  by schedule:\n{sched_lines}\n\n"
        f"🏦 Banks: {total_banks}\n"
        f"📈 Total rates: {total_rates}\n"
        f"🕐 Last collection: {last_str}\n\n"
        f"💾 DB size: {db_size}\n"
        f"⏱ Uptime: {h}h {m}m {s}s"
    )
    await _safe_edit(cb.message, text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "adm:collectors")
async def cb_admin_collectors(cb: CallbackQuery, **kw):
    if not cb.from_user or not _is_admin(cb.from_user.id):
        await cb.answer()
        return

    import collector_stats

    runs = collector_stats.get_all()
    if not runs:
        text = "🔄 No collector data yet."
    else:
        lines = ["🔄 <b>Collector Status</b>\n"]
        for slug, run in sorted(runs.items()):
            icon = "✅" if run.success else "❌"
            lines.append(f"{icon} <b>{slug}</b>: {run.rates_count} rates, {run.duration_ms:.0f}ms")
            if run.error:
                lines.append(f"  ⚠️ {run.error[:80]}")
        text = "\n".join(lines)

    await _safe_edit(cb.message, text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "adm:stale")
async def cb_admin_stale(cb: CallbackQuery, db_session, **kw):
    if not cb.from_user or not _is_admin(cb.from_user.id):
        await cb.answer()
        return

    STALE_THRESHOLD = timedelta(minutes=45)
    now_utc = datetime.now(timezone.utc)
    repo = BankRatesRepo(db_session)
    stale_banks: list[tuple[str, timedelta]] = []
    for code in ("USD", "EUR", "RUB"):
        rates = await repo.latest_by_code(code)
        for r in rates:
            fetched = r.fetched_at
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            age = now_utc - fetched
            if age > STALE_THRESHOLD:
                stale_banks.append((r.bank.name, code, age))

    if not stale_banks:
        text = "✅ All bank data is fresh (< 45 min)."
    else:
        # Dedupe by bank name, show worst age
        seen: dict[str, tuple[str, timedelta]] = {}
        for bname, code, age in stale_banks:
            key = bname
            if key not in seen or age > seen[key][1]:
                seen[key] = (code, age)
        lines = ["⚠️ <b>Stale Bank Data</b>\n"]
        for bname, (code, age) in sorted(seen.items()):
            total_sec = int(age.total_seconds())
            hours, rem = divmod(total_sec, 3600)
            mins = rem // 60
            time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
            lines.append(f"  • <b>{_html.escape(bname)}</b> — {time_str}")
        text = "\n".join(lines)

    await _safe_edit(cb.message, text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "adm:health")
async def cb_admin_health(cb: CallbackQuery, **kw):
    if not cb.from_user or not _is_admin(cb.from_user.id):
        await cb.answer()
        return

    import os
    import subprocess
    import psutil
    import collector_stats

    # ── System metrics ───────────────────────────────────────
    cpu_pct = psutil.cpu_percent(interval=0.5)
    vm = psutil.virtual_memory()
    ram_used = vm.used / (1024 ** 3)
    ram_total = vm.total / (1024 ** 3)
    ram_pct = vm.percent

    disk = psutil.disk_usage("/")
    disk_used = disk.used / (1024 ** 3)
    disk_total = disk.total / (1024 ** 3)
    disk_pct = disk.percent

    # ── Bot process metrics ──────────────────────────────────
    pid = os.getpid()
    try:
        proc = psutil.Process(pid)
        proc_mem_mb = proc.memory_info().rss / (1024 ** 2)
        proc_cpu = proc.cpu_percent(interval=0.2)
        proc_threads = proc.num_threads()
    except psutil.NoSuchProcess:
        proc_mem_mb = proc_cpu = proc_threads = 0.0

    # ── Uptime ───────────────────────────────────────────────
    uptime = collector_stats.uptime_seconds()
    h, rem = divmod(int(uptime), 3600)
    m, s = divmod(rem, 60)
    uptime_str = f"{h}h {m}m {s}s"

    # ── systemd service status ───────────────────────────────
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "kurs-uz-bot"],
            capture_output=True, text=True, timeout=3
        )
        svc_state = result.stdout.strip()
    except Exception:
        svc_state = "unknown"

    svc_icon = "🟢" if svc_state == "active" else "🔴"

    # ── Collector summary ────────────────────────────────────
    runs = collector_stats.get_all()
    total_c = len(runs)
    ok_c = sum(1 for r in runs.values() if r.success)
    if runs:
        last_ts = max(r.timestamp for r in runs.values())
        age_m = int((time.time() - last_ts) / 60)
        age_str = f"{age_m}m ago" if age_m < 60 else f"{age_m // 60}h {age_m % 60}m ago"
    else:
        age_str = "never"

    text = (
        f"🖥️ <b>Server &amp; Bot Health</b>\n\n"
        f"<b>System</b>\n"
        f"  CPU:  {cpu_pct:.1f}%\n"
        f"  RAM:  {ram_used:.1f} / {ram_total:.1f} GB ({ram_pct:.0f}%)\n"
        f"  Disk: {disk_used:.1f} / {disk_total:.1f} GB ({disk_pct:.0f}%)\n\n"
        f"<b>Bot Process  (PID {pid})</b>\n"
        f"  Uptime:  {uptime_str}\n"
        f"  Memory:  {proc_mem_mb:.0f} MB\n"
        f"  CPU:     {proc_cpu:.1f}%\n"
        f"  Threads: {proc_threads}\n\n"
        f"<b>Service</b>\n"
        f"  {svc_icon} kurs-uz-bot: <code>{svc_state}</code>\n\n"
        f"<b>Collectors</b>\n"
        f"  ✅ {ok_c} / {total_c} succeeded\n"
        f"  🕐 Last run: {age_str}"
    )
    await _safe_edit(cb.message, text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "adm:run")
async def cb_admin_run_collectors(cb: CallbackQuery, **kw):
    if not cb.from_user or not _is_admin(cb.from_user.id):
        await cb.answer()
        return

    await cb.answer("⏳ Running collectors...")
    from main import run_collectors
    await run_collectors()

    await _safe_edit(cb.message, "✅ Collectors finished!", reply_markup=admin_keyboard())


# ── /autopost — dynamic channel/group auto-posting ─────────────────────

@router.message(Command("autopost"))
async def cmd_autopost(message: Message, i18n, session, **kw):
    """Channel/group owners add bot as admin, then /autopost to configure."""
    if not message.from_user:
        return

    chat = message.chat
    # Only works in groups/supergroups/channels
    if chat.type == "private":
        await message.answer(i18n("autopost.only-groups"))
        return

    # Check if the user is an admin of this chat
    try:
        member = await message.bot.get_chat_member(chat.id, message.from_user.id)
    except Exception:
        await message.answer(i18n("autopost.error"))
        return

    if member.status not in ("creator", "administrator"):
        await message.answer(i18n("autopost.admin-only"))
        return

    # Check if bot can post messages
    try:
        bot_member = await message.bot.get_chat_member(chat.id, message.bot.id)
    except Exception:
        await message.answer(i18n("autopost.error"))
        return

    can_post = getattr(bot_member, "can_post_messages", None)
    # In supergroups, bot just needs to send messages (always allowed if admin)
    if chat.type == "channel" and not can_post:
        await message.answer(i18n("autopost.need-post-permission"))
        return

    repo = ChannelSubRepo(session)
    sub = await repo.get_or_create(
        chat_id=chat.id,
        title=chat.title or str(chat.id),
        added_by=message.from_user.id,
    )
    await session.commit()

    await message.answer(
        i18n("autopost.configure"),
        reply_markup=autopost_schedule_keyboard(chat.id, sub.schedule),
    )


@router.callback_query(F.data.startswith("autopost:sched:"))
async def cb_autopost_schedule(cb: CallbackQuery, i18n, session, **kw):
    if not cb.from_user:
        await cb.answer()
        return

    parts = cb.data.split(":")
    if len(parts) < 4:
        await cb.answer()
        return
    chat_id = int(parts[2])
    schedule = parts[3]

    repo = ChannelSubRepo(session)
    await repo.set_schedule(chat_id, schedule)
    await session.commit()

    await cb.answer(f"✅ {schedule}")
    await _safe_edit_markup(cb.message, reply_markup=autopost_schedule_keyboard(chat_id, schedule))


@router.callback_query(F.data.startswith("autopost:lang:"))
async def cb_autopost_lang(cb: CallbackQuery, i18n, **kw):
    if not cb.from_user:
        await cb.answer()
        return

    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer()
        return
    chat_id = int(parts[2])

    await cb.answer()
    await _safe_edit(
        cb.message,
        i18n("autopost.choose-lang"),
        reply_markup=autopost_lang_keyboard(chat_id),
    )


@router.callback_query(F.data.startswith("autopost:setlang:"))
async def cb_autopost_setlang(cb: CallbackQuery, i18n, session, **kw):
    if not cb.from_user:
        await cb.answer()
        return

    parts = cb.data.split(":")
    if len(parts) < 4:
        await cb.answer()
        return
    chat_id = int(parts[2])
    lang = parts[3]

    repo = ChannelSubRepo(session)
    await repo.set_lang(chat_id, lang)
    sub = await repo.get_by_chat_id(chat_id)
    await session.commit()

    schedule = sub.schedule if sub else None
    await cb.answer(f"✅ {lang}")
    await _safe_edit(
        cb.message,
        i18n("autopost.configure"),
        reply_markup=autopost_schedule_keyboard(chat_id, schedule),
    )


@router.callback_query(F.data.startswith("autopost:remove:"))
async def cb_autopost_remove(cb: CallbackQuery, i18n, session, **kw):
    if not cb.from_user:
        await cb.answer()
        return

    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer()
        return
    chat_id = int(parts[2])

    repo = ChannelSubRepo(session)
    await repo.remove(chat_id)
    await session.commit()

    await cb.answer("✅ Removed")
    await _safe_edit(cb.message, i18n("autopost.removed"))


# ── Catch-all: unknown text ────────────────────────────────────────────
# Must be registered LAST so it doesn't intercept button presses.

@router.message()
async def msg_unknown(message: Message, i18n, user_repo: UserRepo, **kw):
    if not message.from_user:
        return
    user = await user_repo.get_or_create(message.from_user.id)
    kb = main_keyboard(i18n, bool(user.subscribed))
    await message.answer(i18n("unknown.use-buttons"), reply_markup=kb)
