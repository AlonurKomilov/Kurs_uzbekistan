#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="kurs-uz-bot"
SERVICE_FILE="kurs-uz-bot.service"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "=== Kurs UZ Bot — systemd service installer ==="
echo ""
echo "Project directory: ${PROJECT_DIR}"
echo "Service file:      ${SERVICE_FILE}"
echo ""

# Ensure logs directory exists
mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${PROJECT_DIR}/data"

# Stop the bot if running via Makefile (PID file)
if [ -f "${PROJECT_DIR}/.bot.pid" ]; then
    PID=$(cat "${PROJECT_DIR}/.bot.pid")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping bot running via Makefile (PID ${PID})..."
        kill "$PID" || true
        sleep 2
    fi
    rm -f "${PROJECT_DIR}/.bot.pid"
fi

# Copy service file to systemd
echo "Copying service file to ${SYSTEMD_DIR}/..."
sudo cp "${PROJECT_DIR}/${SERVICE_FILE}" "${SYSTEMD_DIR}/${SERVICE_FILE}"

# Reload systemd daemon
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable the service (auto-start on boot)
echo "Enabling ${SERVICE_NAME} service..."
sudo systemctl enable "${SERVICE_NAME}"

# Start the service
echo "Starting ${SERVICE_NAME} service..."
sudo systemctl start "${SERVICE_NAME}"

# Show status
echo ""
echo "=== Service status ==="
sudo systemctl status "${SERVICE_NAME}" --no-pager || true

echo ""
echo "Done! The bot will now auto-start on server reboot."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status  ${SERVICE_NAME}   # Check status"
echo "  sudo systemctl restart ${SERVICE_NAME}   # Restart"
echo "  sudo systemctl stop    ${SERVICE_NAME}   # Stop"
echo "  sudo journalctl -u     ${SERVICE_NAME} -f  # Live logs"
echo "  tail -f logs/bot.log                      # App logs"
