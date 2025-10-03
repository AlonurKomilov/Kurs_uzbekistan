import os
import re
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, User


class I18nMiddleware(BaseMiddleware):
    """Internationalization middleware for handling user languages."""
    
    def __init__(self):
        self.messages: Dict[str, Dict[str, str]] = {}
        self.supported_locales = ["uz_cy", "ru", "en"]
        self.default_locale = "uz_cy"
        self._load_messages()
    
    def _load_messages(self):
        """Load Fluent localization files."""
        locales_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "locales")
        
        for locale in self.supported_locales:
            locale_file = os.path.join(locales_dir, locale, "messages.ftl")
            if os.path.exists(locale_file):
                self.messages[locale] = self._parse_ftl_file(locale_file)
    
    def _parse_ftl_file(self, file_path: str) -> Dict[str, str]:
        """Simple parser for Fluent files."""
        messages = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # Simple variable substitution for { $var } patterns
                            value = re.sub(r'\{ \$(\w+) \}', r'{\1}', value)
                            messages[key] = value
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        return messages
    
    def _get_user_locale(self, user: User, user_lang: str = None) -> str:
        """Determine user's locale based on DB preference or Telegram language."""
        # If we have a user language preference from DB, use it
        if user_lang and user_lang in self.supported_locales:
            return user_lang
        
        # Map Telegram language codes to supported locales
        tg_lang_map = {
            "uz": "uz_cy",
            "ru": "ru", 
            "en": "en"
        }
        
        # Try to map Telegram language code
        if user.language_code:
            mapped_lang = tg_lang_map.get(user.language_code.lower())
            if mapped_lang:
                return mapped_lang
        
        # Fallback to default
        return self.default_locale
    
    def get_text(self, locale: str, key: str, **kwargs) -> str:
        """Get localized text for the given key."""
        if locale not in self.messages:
            locale = self.default_locale
        
        messages = self.messages.get(locale, {})
        text = messages.get(key, key)
        
        # Simple variable substitution
        try:
            if kwargs:
                text = text.format(**kwargs)
        except KeyError:
            pass  # Ignore missing variables
        
        return text
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """Middleware handler to inject i18n functionality."""
        user = None
        
        # Extract user from different event types
        if hasattr(event, 'from_user'):
            # Direct message or callback query
            user = event.from_user
        elif hasattr(event, 'message') and event.message:
            user = event.message.from_user
        elif hasattr(event, 'callback_query') and event.callback_query:
            user = event.callback_query.from_user
        elif hasattr(event, 'inline_query') and event.inline_query:
            user = event.inline_query.from_user
        
        if user:
            # Get user language from data (will be set by database middleware)
            user_lang = data.get("user_lang")
            locale = self._get_user_locale(user, user_lang)
            
            # Add i18n function to data
            data["i18n"] = lambda key, **kwargs: self.get_text(locale, key, **kwargs)
            data["locale"] = locale
        
        return await handler(event, data)