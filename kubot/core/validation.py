"""Validation utilities for the application."""
import re
from typing import Optional
from urllib.parse import urlparse


def validate_url(url: str, allowed_schemes: Optional[list] = None) -> bool:
    """
    Validate URL format and scheme.
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])
    
    Returns:
        True if valid, False otherwise
    """
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    try:
        result = urlparse(url)
        return all([
            result.scheme in allowed_schemes,
            result.netloc,
            # Prevent common XSS patterns
            not any(char in url for char in ['<', '>', '"', "'"]),
        ])
    except Exception:
        return False


def validate_twa_url(url: str, whitelist: Optional[list] = None) -> bool:
    """
    Validate Telegram Web App URL.
    
    Args:
        url: URL to validate
        whitelist: List of allowed domains (if None, basic validation only)
    
    Returns:
        True if valid, False otherwise
    """
    if not validate_url(url):
        return False
    
    # If whitelist provided, check domain
    if whitelist:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Check if domain matches whitelist
        return any(
            domain == allowed or domain.endswith(f'.{allowed}')
            for allowed in whitelist
        )
    
    return True


def get_validated_twa_url(base_url: str, default: str = "http://localhost:3000") -> str:
    """
    Get validated TWA base URL with fallback.
    
    Args:
        base_url: URL to validate
        default: Default URL if validation fails
    
    Returns:
        Validated URL or default
    """
    # Whitelist of allowed domains for production
    whitelist = [
        'localhost',
        '127.0.0.1',
        'kubot.uz',
        'www.kubot.uz',
    ]
    
    if base_url and validate_twa_url(base_url, whitelist):
        return base_url
    
    return default
