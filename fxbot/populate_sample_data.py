#!/usr/bin/env python3
"""
Script to populate sample bank and rate data for testing.
"""

import sys
import asyncio
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.db import SessionLocal, init_db
from core.repos import BankRatesRepo


async def populate_sample_data():
    """Populate sample banks and rates."""
    print("🏦 Populating sample bank data...")
    
    # Initialize database
    await init_db()
    
    async with SessionLocal() as session:
        bank_repo = BankRatesRepo(session)
        
        # Create sample banks
        banks_data = [
            {"name": "Kapital Bank", "slug": "kapital", "region": "Tashkent", "website": "https://kapitalbank.uz"},
            {"name": "Ipoteka Bank", "slug": "ipoteka", "region": "Tashkent", "website": "https://ipotekabank.uz"},
            {"name": "NBU", "slug": "nbu", "region": "Tashkent", "website": "https://nbu.uz"},
            {"name": "Hamkor Bank", "slug": "hamkor", "region": "Tashkent", "website": "https://hamkorbank.uz"},
            {"name": "Milliy Bank", "slug": "milliy", "region": "Tashkent", "website": "https://milliybank.uz"},
            {"name": "Agrobank", "slug": "agrobank", "region": "Tashkent", "website": "https://agrobank.uz"},
            {"name": "Uzpromstroybank", "slug": "uzpromstroy", "region": "Tashkent", "website": "https://www.uzpsb.uz"},
            {"name": "TBC Bank", "slug": "tbc", "region": "Tashkent", "website": "https://www.tbcbank.uz"},
        ]
        
        created_banks = []
        for bank_data in banks_data:
            # Check if bank already exists
            existing_bank = await bank_repo.get_bank_by_slug(bank_data["slug"])
            if existing_bank:
                print(f"   ✓ Bank {bank_data['name']} already exists")
                created_banks.append(existing_bank)
            else:
                bank = await bank_repo.create_bank(**bank_data)
                print(f"   + Created bank: {bank.name}")
                created_banks.append(bank)
        
        # Create sample rates for each currency
        currencies = ["USD", "EUR", "RUB"]
        
        # Sample rate ranges (buy, sell) - approximating real Uzbekistan rates
        rate_ranges = {
            "USD": (12400, 12500),  # 1 USD = ~12450 UZS
            "EUR": (13500, 13650),  # 1 EUR = ~13575 UZS  
            "RUB": (130, 145),      # 1 RUB = ~137 UZS
        }
        
        print("\n💱 Adding sample rates...")
        
        for currency in currencies:
            print(f"   Adding {currency} rates...")
            base_buy, base_sell = rate_ranges[currency]
            
            for i, bank in enumerate(created_banks):
                # Add some variation to rates for each bank
                buy_variation = (i - 3) * 10  # -30 to +40 range
                sell_variation = (i - 2) * 15  # -30 to +75 range
                
                buy_rate = base_buy + buy_variation
                sell_rate = base_sell + sell_variation
                
                # Ensure sell > buy
                if sell_rate <= buy_rate:
                    sell_rate = buy_rate + 20
                
                rate = await bank_repo.add_rate(
                    bank_id=bank.id,
                    code=currency,
                    buy=buy_rate,
                    sell=sell_rate
                )
                
                print(f"      {bank.name}: {currency} {buy_rate}/{sell_rate}")
        
        print(f"\n✅ Sample data populated successfully!")
        print(f"   Created {len(created_banks)} banks")
        print(f"   Added rates for {len(currencies)} currencies")
        print("\nYou can now test the /start command and Current Rates button!")


if __name__ == "__main__":
    asyncio.run(populate_sample_data())