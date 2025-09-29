#!/bin/bash

# FXBot Development Helper Script

set -e

echo "🤖 FXBot Development Helper"
echo "=========================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env exists
if [ ! -f .env ]; then
    print_warning "No .env file found. Copying from .env.example..."
    cp .env.example .env
    print_warning "Please edit .env file with your actual values!"
fi

# Function to start database
start_db() {
    print_status "Starting PostgreSQL database..."
    docker compose up -d db
    
    # Wait for database to be ready
    print_status "Waiting for database to be ready..."
    sleep 5
    
    # Test connection
    if docker compose exec db pg_isready -U fxbot > /dev/null 2>&1; then
        print_status "Database is ready!"
    else
        print_error "Database failed to start properly"
        exit 1
    fi
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Bot
    if [ -d "bot" ]; then
        print_status "Installing bot dependencies..."
        cd bot && pip install -r requirements.txt && cd ..
    fi
    
    # API
    if [ -d "api" ]; then
        print_status "Installing API dependencies..."
        cd api && pip install -r requirements.txt && cd ..
    fi
    
    # Collectors
    if [ -d "collectors" ]; then
        print_status "Installing collectors dependencies..."
        cd collectors && pip install -r requirements.txt && cd ..
    fi
}

# Function to install Node.js dependencies
install_node_deps() {
    if [ -d "twa" ]; then
        print_status "Installing TWA dependencies..."
        cd twa && npm install && cd ..
    fi
}

# Function to run development services
run_services() {
    print_status "Starting development services..."
    
    # Create tmux session if available
    if command -v tmux &> /dev/null; then
        print_status "Using tmux for session management..."
        
        # Kill existing session if it exists
        tmux kill-session -t fxbot 2>/dev/null || true
        
        # Create new session
        tmux new-session -d -s fxbot
        
        # API
        tmux new-window -t fxbot -n api
        tmux send-keys -t fxbot:api "cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000" Enter
        
        # Bot
        tmux new-window -t fxbot -n bot
        tmux send-keys -t fxbot:bot "cd bot && python main.py" Enter
        
        # Collectors
        tmux new-window -t fxbot -n collectors
        tmux send-keys -t fxbot:collectors "cd collectors && python main.py" Enter
        
        # TWA
        tmux new-window -t fxbot -n twa
        tmux send-keys -t fxbot:twa "cd twa && npm run dev" Enter
        
        print_status "Services started in tmux session 'fxbot'"
        print_status "Use 'tmux attach -t fxbot' to attach to the session"
        print_status "Use 'tmux kill-session -t fxbot' to stop all services"
        
    else
        print_warning "tmux not found. Please run services manually:"
        echo "Terminal 1: cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
        echo "Terminal 2: cd bot && python main.py"
        echo "Terminal 3: cd collectors && python main.py"
        echo "Terminal 4: cd twa && npm run dev"
    fi
}

# Main execution
case "${1:-all}" in
    "db")
        start_db
        ;;
    "deps")
        install_python_deps
        install_node_deps
        ;;
    "python")
        install_python_deps
        ;;
    "node")
        install_node_deps
        ;;
    "services"|"run")
        run_services
        ;;
    "all")
        start_db
        install_python_deps
        install_node_deps
        run_services
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  all       - Setup everything and run services (default)"
        echo "  db        - Start database only"
        echo "  deps      - Install all dependencies"
        echo "  python    - Install Python dependencies only"
        echo "  node      - Install Node.js dependencies only"
        echo "  services  - Run development services"
        echo "  help      - Show this help"
        ;;
    *)
        print_error "Unknown command: $1"
        print_status "Use '$0 help' for available commands"
        exit 1
        ;;
esac

print_status "Done! 🎉"