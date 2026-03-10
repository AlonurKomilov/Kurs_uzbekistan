# kurs_uz_bot

Telegram bot for Uzbekistan bank currency exchange rates (USD / EUR / RUB).

## Banks

| Bank | Source |
|------|--------|
| CBU (Central Bank) | JSON API |
| Kapitalbank | HTML scrape |
| NBU (National Bank) | HTML scrape |
| Ipoteka Bank | HTML scrape |
| Hamkorbank | JSON API |
| TBC Bank | HTML / JSON |
| Turonbank | HTML scrape |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in BOT_TOKEN
python -c "import asyncio; from db import init_db; asyncio.run(init_db())"
python scripts/seed_banks.py
python main.py
```

## Architecture

Single process — bot polling + APScheduler.
- Collectors run every 15 min
- Morning digest at 09:00, evening at 18:00 (Asia/Tashkent)
- Old rate cleanup at 03:00
- SQLite database (no external server needed)

## Tests

```bash
pytest
```
