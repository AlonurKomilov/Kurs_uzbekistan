#!/bin/bash

# FXBot Docker Development Environment
# Simple script to manage Docker containers

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

error() { echo -e "${RED}❌ $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
info() { echo -e "${BLUE}📋 $1${NC}"; }

# Check if .env exists
if [ ! -f .env ]; then
    warning "Creating .env file..."
    cp .env.example .env
    warning "Please edit .env file with your BOT_TOKEN"
    exit 1
fi

# Load environment
source .env

if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    error "Please set BOT_TOKEN in .env file"
    exit 1
fi

case "${1:-up}" in
    "up"|"start")
        info "Starting FXBot services..."
        docker-compose up --build -d
        
        info "Waiting for services to be ready..."
        sleep 10
        
        # Check health
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            success "API is running: http://localhost:8000"
        else
            warning "API not responding yet"
        fi
        
        if curl -s http://localhost:3000 >/dev/null 2>&1; then
            success "TWA is running: http://localhost:3000"
        else
            warning "TWA not responding yet"
        fi
        
        info "Services:"
        info "  API:      http://localhost:8000"
        info "  TWA:      http://localhost:3000"
        info "  Database: localhost:5432"
        ;;
        
    "down"|"stop")
        info "Stopping services..."
        docker-compose down
        success "Services stopped"
        ;;
        
    "restart")
        info "Restarting services..."
        docker-compose down
        docker-compose up --build -d
        success "Services restarted"
        ;;
        
    "logs")
        docker-compose logs -f ${2:-}
        ;;
        
    "status")
        docker-compose ps
        ;;
        
    "clean")
        warning "This will remove all containers and volumes!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down --volumes --remove-orphans
            docker system prune -f
            success "Cleaned up Docker resources"
        fi
        ;;
        
    *)
        echo "Usage: $0 [up|down|restart|logs|status|clean]"
        echo ""
        echo "Commands:"
        echo "  up/start  - Start all services"
        echo "  down/stop - Stop all services"
        echo "  restart   - Restart all services"
        echo "  logs      - Show logs (optional: service name)"
        echo "  status    - Show container status"
        echo "  clean     - Remove all containers and volumes"
        ;;
esac