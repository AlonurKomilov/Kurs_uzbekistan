import hashlib
import math
from datetime import datetime
from typing import List, Optional, Tuple
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from core.repos import BankRatesRepo
from core.models import BankRate
from bot.utils.paging import paginate, get_pagination_info, has_previous_page, has_next_page, PAGE_SIZE

router = Router()

# Supported currencies
SUPPORTED_CURRENCIES = ["USD", "EUR", "RUB"]

# Content hashes cache to prevent unnecessary edits - using SHA256 for better collision resistance
content_hashes = {}

# Configuration
MAX_MESSAGE_LENGTH = 4000  # Leave margin for Telegram's 4096 limit
BANKS_PER_PAGE = PAGE_SIZE  # Use paging utility default
DEFAULT_BANKS_DISPLAY = 5  # Show top 5 by default


def get_content_hash(content: str) -> str:
    """
    Get SHA256 hash of content for efficient change detection.
    
    TODO: Consider implementing differential updates when WebSocket push is available
    to only update changed bank rates instead of full message rebuilds.
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def calculate_message_pages(rates: List[BankRate], banks_per_page: int = BANKS_PER_PAGE) -> int:
    """
    Calculate number of pages needed for the given rates.
    
    TODO: Implement dynamic page sizing based on bank name lengths to maximize
    content per page while staying under 4096 character limit.
    """
    if not rates:
        return 1
    return math.ceil(len(rates) / banks_per_page)


def get_page_rates(rates: List[BankRate], page: int, banks_per_page: int = BANKS_PER_PAGE) -> List[BankRate]:
    """Get rates for specific page."""
    start_idx = (page - 1) * banks_per_page
    end_idx = start_idx + banks_per_page
    return rates[start_idx:end_idx]


def format_bank_table(
    currency: str, 
    rates: List[BankRate], 
    dt_str: str,
    i18n,
    mode: str = 'top',
    limit: Optional[int] = None,
    current_page: int = 1,
    total_pages: int = 1
) -> str:
    """
    Format currency rates as a table.
    
    Args:
        currency: Currency code (USD, EUR, etc.)
        rates: List of bank rates
        dt_str: Time string for "last updated"
        i18n: Internationalization function
        mode: Display mode ('top' or 'page')
        limit: Maximum number of banks to show
        current_page: Current page number
        total_pages: Total number of pages
    """
    if not rates:
        return i18n("rates.no-rates")
    
    message_parts = []
    message_parts.append(f"💱 {i18n('rates.title')} - {currency}")
    message_parts.append(f"🕐 {i18n('rates.last-updated', time=dt_str)}")
    message_parts.append("")
    
    # Show page info for paginated results
    if mode == 'page' and total_pages > 1:
        message_parts.append(f"📄 {get_pagination_info(current_page, total_pages)}")
    
    message_parts.append(f"🏦 {i18n('rates.top-banks')}")
    message_parts.append("")
    
    # Header row
    header = f"{'Bank':<15} {'Buy':<8} {'Sell':<8} {'Δ':<6}"
    message_parts.append(f"`{header}`")
    message_parts.append("```")
    
    # Show rates for current view
    display_rates = rates
    if limit:
        display_rates = rates[:limit]
    
    # Format each bank rate
    for rate in display_rates:
        bank_name = rate.bank.name[:12] if len(rate.bank.name) > 12 else rate.bank.name
        buy_rate = f"{float(getattr(rate, 'buy')):,.0f}"
        sell_rate = f"{float(getattr(rate, 'sell')):,.0f}"
        delta = float(getattr(rate, 'sell')) - float(getattr(rate, 'buy'))
        delta_str = f"{delta:+.0f}"
        
        row = f"{bank_name:<15} {buy_rate:<8} {sell_rate:<8} {delta_str:<6}"
        message_parts.append(row)
    
    message_parts.append("```")
    message_parts.append("")
    message_parts.append(f"ℹ️ {i18n('rates.disclaimer')}")
    
    return "\n".join(message_parts)


def build_tabs_with_paging(
    currency: str, 
    current_page: int, 
    total_pages: int, 
    i18n,
    show_all: bool = False
) -> InlineKeyboardMarkup:
    """
    Build keyboard with currency tabs and paging buttons.
    
    Args:
        currency: Current currency
        current_page: Current page number
        total_pages: Total number of pages
        i18n: Internationalization function
        show_all: Whether showing all results or just top
    """
    keyboard = []
    
    # Currency tabs row
    currency_row = []
    for curr in SUPPORTED_CURRENCIES:
        text = f"{'🔸' if curr == currency else '▫️'} {curr}"
        callback_data = f"cr:{curr}:{'all' if show_all else 'top'}"
        currency_row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    keyboard.append(currency_row)
    
    # Navigation buttons for paginated view
    if show_all and total_pages > 1:
        nav_row = []
        
        # Previous page button
        if has_previous_page(current_page):
            nav_row.append(InlineKeyboardButton(
                text="◀️ Prev",
                callback_data=f"cr:{currency}:p{current_page - 1}"
            ))
        
        # Page indicator
        nav_row.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="noop"  # Non-clickable indicator
        ))
        
        # Next page button
        if has_next_page(current_page, total_pages):
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️",
                callback_data=f"cr:{currency}:p{current_page + 1}"
            ))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Back to TOP button for paginated view
        keyboard.append([
            InlineKeyboardButton(
                text="🔝 Back to Top",
                callback_data=f"cr:{currency}:top"
            )
        ])
    else:
        # More/Back button row for non-paginated view
        if show_all:
            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data=f"cr:{currency}:top"
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    text="📋 Show All", 
                    callback_data=f"cr:{currency}:all"
                )
            ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def format_rate_message(
    rates: List[BankRate], 
    currency: str, 
    i18n, 
    show_all: bool = False,
    current_page: int = 1,
    total_pages: int = 1
) -> str:
    """
    Legacy format function for compatibility.
    """
    return format_bank_table(
        currency, rates, datetime.now().strftime("%H:%M"), 
        i18n, mode='page' if show_all else 'top',
        limit=DEFAULT_BANKS_DISPLAY if not show_all else None,
        current_page=current_page, total_pages=total_pages
    )


def create_currency_tabs_keyboard(
    i18n, 
    current_currency: str = "USD", 
    show_all: bool = False,
    current_page: int = 1,
    total_pages: int = 1
) -> InlineKeyboardMarkup:
    """
    Legacy keyboard function for compatibility.
    """
    return build_tabs_with_paging(current_currency, current_page, total_pages, i18n, show_all)


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


@router.callback_query(F.data.startswith("cr:"))
async def currency_rates_callback_handler(callback_query: CallbackQuery, i18n, db_session, **kwargs):
    """
    Handle currency rates callback queries with paging support.
    
    Supports:
    - cr:USD:top - Show top banks for USD
    - cr:USD:all - Show all banks for USD (first page)
    - cr:USD:p2 - Show page 2 for USD
    """
    try:
        # Parse callback data: cr:USD:top, cr:USD:all, or cr:USD:p2
        if not callback_query.data:
            await callback_query.answer("❌ Invalid request")
            return
            
        parts = callback_query.data.split(":")
        if len(parts) < 3:
            await callback_query.answer("❌ Invalid request")
            return
            
        _, currency, mode_or_page = parts
        
        # Validate currency
        if currency not in SUPPORTED_CURRENCIES:
            await callback_query.answer("❌ Unsupported currency")
            return
        
        # Parse mode/page using the simplified logic from user request
        show_all = False
        page = 1
        mode = "top"
        
        if mode_or_page == "top":
            show_all = False
            mode = "top"
        elif mode_or_page == "all":
            show_all = True
            page = 1
            mode = "page"
        elif mode_or_page.startswith("p"):
            show_all = True
            try:
                page = int(mode_or_page[1:])
                if page < 1:
                    page = 1
                mode = "page"
            except ValueError:
                await callback_query.answer("❌ Invalid page number")
                return
        else:
            await callback_query.answer("❌ Invalid mode")
            return
        
        bank_rates_repo = BankRatesRepo(db_session)
        
        # Get rates for the requested currency
        all_rates = await bank_rates_repo.latest_by_code(currency)
        
        if not all_rates:
            text = format_rate_message([], currency, i18n, show_all=show_all)
            keyboard = build_tabs_with_paging(currency, 1, 1, i18n, show_all=show_all)
        else:
            if show_all:
                # Use paging utility
                page_rates, current_page, total_pages = paginate(all_rates, page, BANKS_PER_PAGE)
                
                # Format message with page information
                text = format_bank_table(
                    currency, page_rates, datetime.now().strftime("%H:%M"), 
                    i18n, mode='page', limit=len(page_rates),
                    current_page=current_page, total_pages=total_pages
                )
                
                # Create keyboard with pagination
                keyboard = build_tabs_with_paging(currency, current_page, total_pages, i18n, show_all=True)
            else:
                # Show top banks only
                text = format_bank_table(currency, all_rates, datetime.now().strftime("%H:%M"), i18n, mode='top', limit=DEFAULT_BANKS_DISPLAY)
                keyboard = build_tabs_with_paging(currency, 1, 1, i18n, show_all=False)
        
        # Check if content has changed using SHA256 (improved from MD5)
        if not callback_query.message or not callback_query.from_user:
            await callback_query.answer("❌ Invalid request")
            return
            
        content_key = f"{callback_query.from_user.id}:{callback_query.message.message_id}"
        new_hash = get_content_hash(text)
        old_hash = content_hashes.get(content_key)
        
        if new_hash == old_hash:
            # Content hasn't changed, just answer callback to remove loading state
            await callback_query.answer()
            return
        
        # Update content hash
        content_hashes[content_key] = new_hash
        
        # Check message length (Telegram limit is 4096 characters)
        if len(text) > MAX_MESSAGE_LENGTH:
            # TODO: Implement smarter content splitting that preserves complete bank entries
            # For now, truncate with warning
            text = text[:MAX_MESSAGE_LENGTH] + "\n\n_... (Content truncated - too many banks)_"
        
        # Edit message with improved error handling
        try:
            from aiogram.types import Message
            if isinstance(callback_query.message, Message):
                await callback_query.message.edit_text(
                    text, 
                    reply_markup=keyboard, 
                    parse_mode="Markdown"
                )
            else:
                # Message is inaccessible, can't edit or send
                await callback_query.answer("❌ Cannot update message")
                return
        except Exception as edit_error:
            # If edit fails, answer with error
            await callback_query.answer("❌ Failed to update message")
        
        # Answer callback to remove loading state
        await callback_query.answer()
        
    except Exception as e:
        print(f"Error in currency rates callback: {e}")
        await callback_query.answer("❌ Error occurred")


@router.callback_query(lambda c: c.data == "noop")
async def noop_callback_handler(callback_query: CallbackQuery, **kwargs):
    """Handle non-interactive callback queries (like page indicators)."""
    await callback_query.answer()