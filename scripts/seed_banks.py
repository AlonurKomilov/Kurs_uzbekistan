"""Seed the banks table with all supported banks."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_session  # noqa: E402
from repos import BankRatesRepo  # noqa: E402

BANKS = [
    ("cbu", "Central Bank", "https://cbu.uz"),
    ("kapitalbank", "Kapitalbank", "https://kapitalbank.uz"),
    ("nbu", "National Bank", "https://nbu.uz"),
    ("ipoteka", "Ipoteka Bank", "https://www.ipotekabank.uz"),
    ("hamkorbank", "Hamkorbank", "https://hamkorbank.uz"),
    ("tbc", "TBC Bank", "https://tbcbank.uz"),
    ("turonbank", "Turonbank", "https://turonbank.uz"),
    ("aloqabank", "Aloqabank", "https://aloqabank.uz"),
    ("trastbank", "Trastbank", "https://trastbank.uz"),
    ("poytaxtbank", "Poytaxt Bank", "https://poytaxtbank.uz"),
    ("kdbbank", "KDB Bank", "https://kdb.uz"),
    # Banks sourced from kurs.uz aggregator
    ("aab", "Asia Alliance Bank", "https://aab.uz"),
    ("agrobank", "Agrobank", "https://agrobank.uz"),
    ("infinbank", "InFinBank", "https://infinbank.uz"),
    ("ofb", "Orient Finance Bank", "https://ofb.uz"),
    ("sqb", "Sanoat Qurilish Bank", "https://sqb.uz"),
    ("xalqbank", "Xalq Bank", "https://xalqbank.uz"),
    ("tengebank", "Tengebank", "https://tengebank.uz"),
    ("universalbank", "Universal Bank", "https://universalbank.uz"),
    ("ipakyulibank", "Ipak Yo'li Bank", "https://ipakyulibank.uz"),
]


async def seed():
    async with get_session() as session:
        repo = BankRatesRepo(session)
        for slug, name, website in BANKS:
            existing = await repo.get_bank_by_slug(slug)
            if existing:
                print(f"  exists: {slug}")
            else:
                from models import Bank

                bank = Bank(name=name, slug=slug, website=website)
                session.add(bank)
                print(f"  created: {slug}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
