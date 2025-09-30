#!/bin/bash

# FXBot Development Stack - Simple startup script

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

error() { echo -e "${RED}❌ $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
info() { echo -e "${BLUE}📋 $1${NC}"; }

# Create directories
mkdir -p logs pids

# Check environment
if [ ! -f .env ]; then
    warning "Creating .env template..."
    cat > .env << 'EOF'
BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://fxbot:password@localhost:5432/fxbot
POSTGRES_USER=fxbot
POSTGRES_PASSWORD=password
POSTGRES_DB=fxbot
EOF
    warning "Please edit .env with your BOT_TOKEN"
    exit 1
fi

source .env

if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    error "BOT_TOKEN not configured in .env"
    exit 1
fi

# Handle commands
case "${1:-start}" in
    "stop")
        info "Stopping services..."
        for pidfile in pids/*.pid; do
            [ -f "$pidfile" ] && kill $(cat "$pidfile") 2>/dev/null || true
            rm -f "$pidfile"
        done
        docker stop fxbot-postgres 2>/dev/null || true
        success "Services stopped"
        exit 0
        ;;
    "status")
        info "Checking service status..."
        
        if docker ps | grep -q fxbot-postgres; then
            success "✓ PostgreSQL: Running"
        else
            error "✗ PostgreSQL: Stopped"
        fi
        
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            success "✓ API: Running"
        else
            error "✗ API: Not responding"
        fi
        
        if [ -f "pids/bot.pid" ] && kill -0 $(cat pids/bot.pid) 2>/dev/null; then
            success "✓ Bot: Running"
        else
            error "✗ Bot: Stopped"
        fi
        
        exit 0
        ;;
esac

info "🚀 Starting FXBot Development Stack"

# Cleanup on exit
cleanup() {
    info "Cleaning up..."
    for pidfile in pids/*.pid; do
        [ -f "$pidfile" ] && kill $(cat "$pidfile") 2>/dev/null || true
        rm -f "$pidfile"
    done
    docker stop fxbot-postgres 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start PostgreSQL
info "Starting PostgreSQL..."
docker rm -f fxbot-postgres 2>/dev/null || true
docker run -d --name fxbot-postgres \
    -e POSTGRES_USER=${POSTGRES_USER:-fxbot} \
    -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password} \
    -e POSTGRES_DB=${POSTGRES_DB:-fxbot} \
    -p 5432:5432 postgres:15 >/dev/null
sleep 5
success "PostgreSQL started"

# Setup Python
info "Setting up Python..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q aiogram fastapi uvicorn sqlalchemy asyncpg python-dotenv apscheduler aiohttp
success "Python environment ready"

# Start API
info "Starting API..."
cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ../logs/api.log 2>&1 &
echo $! > ../pids/api.pid
cd ..
sleep 3
success "API started"

# Start Bot
info "Starting Bot..."
export PYTHONPATH="/workspaces/Kurs_uzbekistan/fxbot:$PYTHONPATH"
python bot/main.py > logs/bot.log 2>&1 &
echo $! > pids/bot.pid
sleep 3
success "Bot started"

# Start Collectors
info "Starting Collectors..."
export PYTHONPATH="/workspaces/Kurs_uzbekistan/fxbot:$PYTHONPATH"
python collectors/main.py > logs/collectors.log 2>&1 &
echo $! > pids/collectors.pid
sleep 2
success "Collectors started"

echo
success "🎉 Development stack is running!"
echo
info "Services:"
info "  API:      http://localhost:8000"
info "  Health:   http://localhost:8000/api/health"
info "  Database: localhost:5432"
echo
info "Logs:"
info "  API:        logs/api.log"
info "  Bot:        logs/bot.log"
info "  Collectors: logs/collectors.log"
echo
warning "Press Ctrl+C to stop all services"

# Keep running
while true; do
    sleep 10
done
