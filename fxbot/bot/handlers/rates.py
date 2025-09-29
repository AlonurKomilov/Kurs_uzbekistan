import hashlib
from datetime import datetime
from typing import List, Optional
from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from core.repos import BankRatesRepo
from core.models import BankRate

router = Router()

# Supported currencies
SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB"]

# Content hashes cache to prevent unnecessary edits
content_hashes = {}


def get_content_hash(content: str) -> str:
    """Get MD5 hash of content for flood control."""
    return hashlib.md5(content.encode()).hexdigest()


def create_currency_tabs_keyboard(i18n, current_currency: str = "USD", show_all: bool = False) -> InlineKeyboardMarkup:
    """Create inline keyboard with currency tabs and more/back buttons."""
    keyboard = []
    
    # Currency tabs row
    currency_row = []
    for currency in SUPPORTED_CURRENCIES:
        text = f"{'🔸' if currency == current_currency else '▫️'} {currency}"
        callback_data = f"cr:{currency}:{'all' if show_all else 'top'}"
        currency_row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    keyboard.append(currency_row)
    
    # More/Back button row
    if show_all:
        keyboard.append([
            InlineKeyboardButton(
                text=i18n("rates.back"),
                callback_data=f"cr:{current_currency}:top"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text=i18n("rates.more"), 
                callback_data=f"cr:{current_currency}:all"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def format_rate_message(rates: List[BankRate], currency: str, i18n, show_all: bool = False) -> str:
    """Format currency rates message."""
    if not rates:
        return i18n("rates.no-rates")
    
    # Get current time for "last updated"
    current_time = datetime.now().strftime("%H:%M")
    
    message_parts = []
    message_parts.append(f"💱 {i18n('rates.title')} - {currency}")
    message_parts.append(f"🕐 {i18n('rates.last-updated', time=current_time)}")
    message_parts.append("")
    message_parts.append(f"🏦 {i18n('rates.top-banks')}")
    message_parts.append("")
    
    # Header row
    header = f"{'Bank':<15} {'Buy':<8} {'Sell':<8} {'Δ':<6}"
    message_parts.append(f"`{header}`")
    message_parts.append("```")
    
    # Determine how many rates to show
    limit = len(rates) if show_all else min(5, len(rates))
    display_rates = rates[:limit]
    
    # Calculate delta (difference between sell and buy)
    for rate in display_rates:
        bank_name = rate.bank.name[:12] if len(rate.bank.name) > 12 else rate.bank.name
        buy_rate = f"{float(rate.buy):,.0f}"
        sell_rate = f"{float(rate.sell):,.0f}"
        delta = float(rate.sell) - float(rate.buy)
        delta_str = f"{delta:+.0f}"
        
        row = f"{bank_name:<15} {buy_rate:<8} {sell_rate:<8} {delta_str:<6}"
        message_parts.append(row)
    
    message_parts.append("```")
    
    # Add summary if showing limited results
    if not show_all and len(rates) > 5:
        message_parts.append(f"_... and {len(rates) - 5} more banks_")
    
    return "\n".join(message_parts)


@router.message(lambda message: message.text and any(
    phrase in message.text for phrase in [
        "Current Rates", "Ҳозирги курслар", "Текущие курсы", 
        "⏱️ Current Rates", "⏱️ Ҳозирги курслар", "⏱️ Текущие курсы"
    ]
))
async def current_rates_handler(message: Message, i18n, db_session, **kwargs):
    """Handle current rates button click."""
    bank_rates_repo = BankRatesRepo(db_session)
    
    # Get rates for default currency (USD)
    rates = await bank_rates_repo.latest_by_code("USD")
    
    # Format message
    text = format_rate_message(rates, "USD", i18n, show_all=False)
    
    # Create keyboard
    keyboard = create_currency_tabs_keyboard(i18n, "USD", show_all=False)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(lambda c: c.data and c.data.startswith("cr:"))
async def currency_rates_callback_handler(callback_query: CallbackQuery, i18n, db_session, **kwargs):
    """Handle currency rates callback queries."""
    try:
        # Parse callback data: cr:USD:top or cr:USD:all
        parts = callback_query.data.split(":")
        if len(parts) != 3:
            await callback_query.answer("❌ Invalid request")
            return
            
        _, currency, mode = parts
        show_all = mode == "all"
        
        # Validate currency
        if currency not in SUPPORTED_CURRENCIES:
            await callback_query.answer("❌ Unsupported currency")
            return
        
        bank_rates_repo = BankRatesRepo(db_session)
        
        # Get rates for the requested currency
        rates = await bank_rates_repo.latest_by_code(currency)
        
        # Format message
        text = format_rate_message(rates, currency, i18n, show_all=show_all)
        
        # Create keyboard
        keyboard = create_currency_tabs_keyboard(i18n, currency, show_all=show_all)
        
        # Check if content has changed (flood control)
        content_key = f"{callback_query.from_user.id}:{callback_query.message.message_id}"
        new_hash = get_content_hash(text)
        old_hash = content_hashes.get(content_key)
        
        if new_hash == old_hash:
            # Content hasn't changed, just answer callback
            await callback_query.answer()
            return
        
        # Update content hash
        content_hashes[content_key] = new_hash
        
        # Check message length (Telegram limit is 4096 characters)
        if len(text) > 4000:  # Leave some margin for safety
            # TODO: Implement pagination for very long messages (cr:USD:p2)
            text = text[:4000] + "\n\n_... (Message truncated)_"
        
        # Edit message
        await callback_query.message.edit_text(
            text, 
            reply_markup=keyboard, 
            parse_mode="Markdown"
        )
        
        # Answer callback
        await callback_query.answer()
        
    except Exception as e:
        print(f"Error in currency rates callback: {e}")
        await callback_query.answer("❌ Error occurred")