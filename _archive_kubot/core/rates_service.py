"""
Rates service for generating daily digest content.
"""
import asyncio
from datetime import datetime, date
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.repos import BankRatesRepo
from core.models import BankRate


class RatesService:
    """Service for handling currency rates and generating digest content."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.rates_repo = BankRatesRepo(session)
    
    async def get_daily_bundle(self) -> Dict[str, List[BankRate]]:
        """Get daily rates bundle for USD, EUR, RUB."""
        currencies = ['USD', 'EUR', 'RUB']
        bundle = {}
        
        for currency in currencies:
            rates = await self.rates_repo.latest_by_code(currency)
            if rates:
                # Get top 5 rates for digest
                bundle[currency] = rates[:5]
            else:
                bundle[currency] = []
        
        return bundle
    
    def format_digest_message(self, bundle: Dict[str, List[BankRate]], lang: str = 'en') -> str:
        """Format daily digest message in specified language."""
        today = datetime.now().strftime('%d.%m.%Y')
        
        # Language-specific headers
        headers = {
            'en': f"💰 Daily Rates - {today}",
            'ru': f"💰 Дневные курсы - {today}",
            'uz_cy': f"💰 Кунлик курслар - {today}"
        }
        
        # Currency symbols
        symbols = {
            'USD': '🇺🇸 USD',
            'EUR': '🇪🇺 EUR', 
            'RUB': '🇷🇺 RUB'
        }
        
        message_parts = [headers.get(lang, headers['en'])]
        message_parts.append('')  # Empty line
        
        for currency, rates in bundle.items():
            if not rates:
                continue
                
            message_parts.append(f"{symbols[currency]}:")
            
            # Get best and average rates
            sell_rates = [float(getattr(rate, 'sell')) for rate in rates]
            best_rate = min(sell_rates)
            avg_rate = sum(sell_rates) / len(sell_rates)
            
            if lang == 'en':
                message_parts.append(f"  💎 Best: {best_rate:,.0f}")
                message_parts.append(f"  📊 Avg: {avg_rate:,.0f}")
            elif lang == 'ru':
                message_parts.append(f"  💎 Лучший: {best_rate:,.0f}")
                message_parts.append(f"  📊 Средний: {avg_rate:,.0f}")
            elif lang == 'uz_cy':
                message_parts.append(f"  💎 Энг яхши: {best_rate:,.0f}")
                message_parts.append(f"  📊 Ўртача: {avg_rate:,.0f}")
            
            message_parts.append('')  # Empty line
        
        # Add footer
        footer_texts = {
            'en': "🕘 Updated this morning",
            'ru': "🕘 Обновлено утром", 
            'uz_cy': "🕘 Эрталаб янгиланди"
        }
        
        message_parts.append(footer_texts.get(lang, footer_texts['en']))
        
        return '\n'.join(message_parts)
    
    def get_digest_keyboard(self, lang: str = 'en', user_lang: str | None = None):
        """Get inline keyboard for digest message."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
        import os
        from core.validation import get_validated_twa_url
        
        if user_lang is None:
            user_lang = lang
            
        # Get validated TWA base URL
        twa_base_url = get_validated_twa_url(os.getenv("TWA_BASE_URL", ""))
        
        # Button texts
        button_texts = {
            'en': {'refresh': '🔄 Refresh', 'live': '🟢 Live Rates'},
            'ru': {'refresh': '🔄 Обновить', 'live': '🟢 Живой курс'},
            'uz_cy': {'refresh': '🔄 Янгилаш', 'live': '🟢 Жонли курс'}
        }
        
        texts = button_texts.get(lang, button_texts['en'])
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts['refresh'],
                        callback_data="refresh_rates"
                    ),
                    InlineKeyboardButton(
                        text=texts['live'],
                        web_app=WebAppInfo(url=f"{twa_base_url}/twa?lang={user_lang}")
                    )
                ]
            ]
        )
        
        return keyboard


async def get_rates_service() -> RatesService:
    """Get rates service instance."""
    from infrastructure.db import SessionLocal
    session = SessionLocal()
    return RatesService(session)