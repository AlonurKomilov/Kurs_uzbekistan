"""
Populate banks table with initial data
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.repos import BankRatesRepo
from infrastructure.db import SessionLocal

# Bank configurations from commercial_banks.py
BANKS = [
    {
        "name": "Central Bank of Uzbekistan (CBU)",
        "slug": "cbu",
        "region": "National",
        "website": "https://cbu.uz"
    },
    {
        "name": "National Bank of Uzbekistan",
        "slug": "nbu",
        "region": "National",
        "website": "https://nbu.uz"
    },
    {
        "name": "Ipoteka Bank",
        "slug": "ipoteka",
        "region": "National",
        "website": "https://www.ipotekabank.uz"
    },
    {
        "name": "Hamkorbank",
        "slug": "hamkorbank",
        "region": "National",
        "website": "https://www.hamkorbank.uz"
    },
    {
        "name": "Kapitalbank",
        "slug": "kapitalbank",
        "region": "National",
        "website": "https://kapitalbank.uz"
    },
    {
        "name": "Qishloq Qurilish Bank",
        "slug": "qishloq",
        "region": "National",
        "website": "https://www.qqb.uz"
    },
    {
        "name": "TBC Bank Uzbekistan",
        "slug": "tbc",
        "region": "National",
        "website": "https://www.tbcbank.uz"
    },
    {
        "name": "Turonbank",
        "slug": "turonbank",
        "region": "National",
        "website": "https://www.turonbank.uz"
    },
    {
        "name": "Universal Bank",
        "slug": "universal",
        "region": "National",
        "website": "https://universalbank.uz"
    }
]


async def populate_banks():
    """Populate banks table with initial data."""
    async with SessionLocal() as session:
        repo = BankRatesRepo(session)
        
        print("Populating banks...")
        for bank_data in BANKS:
            try:
                # Check if bank already exists
                existing = await repo.get_bank_by_slug(bank_data["slug"])
                if existing:
                    print(f"  ✓ Bank already exists: {bank_data['name']}")
                    continue
                
                # Create new bank
                bank = await repo.create_bank(**bank_data)
                print(f"  ✅ Created: {bank_data['name']} (ID: {bank.id})")
            except Exception as e:
                print(f"  ❌ Error creating {bank_data['name']}: {e}")
        
        await session.commit()
        print("\n✅ Banks population complete!")


if __name__ == "__main__":
    print("=" * 60)
    print("Bank Database Population Script")
    print("=" * 60)
    print()
    
    asyncio.run(populate_banks())
