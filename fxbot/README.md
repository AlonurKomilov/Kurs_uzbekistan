# FXBot - Currency Exchange Bot

A modern monorepo for a Telegram bot that provides currency exchange rates with FastAPI backend, Next.js web app, and data collectors.

## Tech Stack

- **Bot**: Python 3.11 + aiogram v3
- **API**: FastAPI + SQLAlchemy async + asyncpg
- **TWA**: Next.js 14 + i18next
- **Database**: PostgreSQL 16
- **Collectors**: APScheduler + httpx

## Quick Start

1. Copy environment variables:
```bash
cp .env.example .env
```

2. Start the database:
```bash
docker compose up -d db
```

3. Install Python dependencies:
```bash
# Bot
cd bot && pip install -r requirements.txt

# API
cd ../api && pip install -r requirements.txt

# Collectors
cd ../collectors && pip install -r requirements.txt
```

4. Install TWA dependencies:
```bash
cd twa && npm install
```

5. Run services individually:
```bash
# Bot
cd bot && python main.py

# API
cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Collectors
cd collectors && python main.py

# TWA
cd twa && npm run dev
```

## Development

Use the development script for easier local development:
```bash
./scripts/dev.sh
```

## Structure

- `bot/` - Telegram bot with aiogram v3
- `api/` - FastAPI backend service
- `twa/` - Next.js Telegram Web App
- `collectors/` - Data collection services
- `core/` - Shared business logic
- `infrastructure/` - Database and external services
- `locales/` - Localization files (Fluent format)
- `scripts/` - Utility scripts