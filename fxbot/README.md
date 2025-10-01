# KUBot - Uzbekistan Currency Exchange Bot# KUBot - Currency Exchange Bot



Telegram bot for real-time currency exchange rates in Uzbekistan with multi-language support and web app interface.A modern monorepo for a Telegram bot that provides currency exchange rates with FastAPI backend, Next.js web app, and data collectors.



## 🚀 Quick Start## Tech Stack



1. **Clone the repository:**- **Bot**: Python 3.11 + aiogram v3

   ```bash- **API**: FastAPI + SQLAlchemy async + asyncpg

   git clone <repository-url>- **TWA**: Next.js 14 + i18next

   cd fxbot- **Database**: PostgreSQL 16

   ```- **Collectors**: APScheduler + httpx



2. **Configure environment:**## Quick Start

   ```bash

   cp .env.example .env1. Copy environment variables:

   # Edit .env and set your BOT_TOKEN```bash

   ```cp .env.example .env

```

3. **Start with Docker:**

   ```bash2. Start the database:

   ./docker-dev.sh up```bash

   ```docker compose up -d db

```

That's it! The bot, API, database, and web app are now running.

3. Install Python dependencies:

## 📋 Services```bash

# Bot

- **Telegram Bot**: Handles user interactionscd bot && pip install -r requirements.txt

- **API**: REST API at http://localhost:8000

- **TWA**: Web app at http://localhost:3000  # API

- **Database**: PostgreSQL at localhost:5432cd ../api && pip install -r requirements.txt



## 🛠 Development Commands# Collectors

cd ../collectors && pip install -r requirements.txt

```bash```

# Start all services

./docker-dev.sh up4. Install TWA dependencies:

```bash

# Stop all servicescd twa && npm install

./docker-dev.sh down```



# View logs5. Run services individually:

./docker-dev.sh logs```bash

# Bot

# Check statuscd bot && python main.py

./docker-dev.sh status

# API

# Clean restartcd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

./docker-dev.sh clean

./docker-dev.sh up# Collectors

```cd collectors && python main.py



## 🌐 Features# TWA

cd twa && npm run dev

- **Multi-language support**: Uzbek (Cyrillic/Latin), Russian, English```

- **Real-time rates**: Live data from Central Bank of Uzbekistan

- **Telegram Web App**: Modern web interface## Development

- **Subscriptions**: Daily digest notifications

- **Bank comparison**: Compare rates across multiple banksUse the development script for easier local development:

```bash

## 🏗 Architecture./scripts/dev.sh

```

```

├── api/           # FastAPI REST API## Structure

├── bot/           # Telegram bot handlers

├── twa/           # Next.js web application- `bot/` - Telegram bot with aiogram v3

├── core/          # Shared models and business logic- `api/` - FastAPI backend service

├── infrastructure/# Database and shared infrastructure- `twa/` - Next.js Telegram Web App

├── collectors/    # Rate collection services- `collectors/` - Data collection services

└── locales/       # Translation files- `core/` - Shared business logic

```- `infrastructure/` - Database and external services

- `locales/` - Localization files (Fluent format)

## 🔧 Environment Variables- `scripts/` - Utility scripts

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql+asyncpg://kubot:kubot_password@db:5432/kubot
```

## 📱 Bot Commands

- `/start` - Start the bot
- `/rates` - Get current rates
- `/subscribe` - Toggle daily digest
- `/lang` - Change language
- `/help` - Show help

## 🌍 Supported Languages

- `uz_cy` - Uzbek (Cyrillic)
- `uz_la` - Uzbek (Latin) 
- `ru` - Russian
- `en` - English

## 🏦 Data Sources

- Central Bank of Uzbekistan (CBU)
- Commercial banks (planned)

## 📦 Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **Bot**: aiogram 3.x
- **Frontend**: Next.js, TypeScript, Tailwind CSS
- **Infrastructure**: Docker, Docker Compose

## 🚦 Health Checks

- API Health: http://localhost:8000/health
- Database connectivity included in health checks

## 📄 License

MIT License