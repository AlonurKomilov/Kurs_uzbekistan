# bot/utils/paging.py
"""
Utility for paginating long lists in Telegram bot messages.
Prevents exceeding the 4096 character limit and provides navigation.
"""

from typing import List, Tuple, TypeVar

T = TypeVar('T')

# Default page size to keep messages under 4096 character limit
PAGE_SIZE = 10


def paginate(items: List[T], page: int = 1, page_size: int = PAGE_SIZE) -> Tuple[List[T], int, int]:
    """
    Paginate a list of items.
    
    Args:
        items: List of items to paginate
        page: Current page number (1-based)
        page_size: Number of items per page
        
    Returns:
        Tuple of (page_items, current_page, total_pages)
    """
    total = len(items)
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    # Ensure page is within valid range
    page = max(1, min(page, total_pages))
    
    # Calculate start and end indices
    start = (page - 1) * page_size
    end = start + page_size
    
    # Get items for current page
    page_items = items[start:end]
    
    return page_items, page, total_pages


def get_pagination_info(current_page: int, total_pages: int) -> str:
    """
    Get pagination info string for display.
    
    Args:
        current_page: Current page number
        total_pages: Total number of pages
        
    Returns:
        Pagination info string (e.g., "Page 1 of 5")
    """
    return f"Page {current_page} of {total_pages}"


def has_previous_page(current_page: int) -> bool:
    """Check if there's a previous page."""
    return current_page > 1


def has_next_page(current_page: int, total_pages: int) -> bool:
    """Check if there's a next page."""
    return current_page < total_pages