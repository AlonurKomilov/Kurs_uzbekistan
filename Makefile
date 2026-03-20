# ── KUBot Makefile ────────────────────────────────────────────────────────
PYTHON  := .venv/bin/python3
APP     := main.py
PID_FILE:= .bot.pid
SERVICE := kurs-uz-bot

.PHONY: start stop restart clean status logs

## start — start the bot (via systemd if installed, otherwise nohup fallback)
start:
	@if systemctl is-active --quiet $(SERVICE) 2>/dev/null; then \
		echo "Bot already running via systemd ($(SERVICE))"; \
	elif systemctl list-unit-files $(SERVICE).service 2>/dev/null | grep -q $(SERVICE); then \
		sudo systemctl start $(SERVICE) && echo "Bot started via systemd"; \
	else \
		echo "[fallback] systemd service not installed, using nohup..."; \
		if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
			echo "Bot already running (PID $$(cat $(PID_FILE)))"; \
		else \
			mkdir -p logs data; \
			nohup $(PYTHON) $(APP) >> logs/bot.log 2>&1 & echo $$! > $(PID_FILE); \
			echo "Bot started (PID $$(cat $(PID_FILE)))"; \
		fi; \
	fi

## stop — stop the bot (via systemd if installed)
stop:
	@if systemctl list-unit-files $(SERVICE).service 2>/dev/null | grep -q $(SERVICE); then \
		sudo systemctl stop $(SERVICE) && echo "Bot stopped via systemd"; \
	else \
		echo "[fallback] Stopping via PID file..."; \
		if [ -f $(PID_FILE) ]; then \
			PID=$$(cat $(PID_FILE)); \
			if kill -0 $$PID 2>/dev/null; then \
				kill $$PID && echo "Bot stopped (PID $$PID)"; \
			else \
				echo "Bot not running (stale PID file)"; \
			fi; \
			rm -f $(PID_FILE); \
		else \
			PID=$$(pgrep -f "python.*$(APP)" | head -1); \
			if [ -n "$$PID" ]; then \
				kill $$PID && echo "Bot stopped (PID $$PID)"; \
			else \
				echo "Bot is not running"; \
			fi; \
		fi; \
	fi

## restart — restart the bot (via systemd if installed)
restart:
	@if systemctl list-unit-files $(SERVICE).service 2>/dev/null | grep -q $(SERVICE); then \
		sudo systemctl restart $(SERVICE) && echo "Bot restarted via systemd"; \
	else \
		$(MAKE) stop && sleep 1 && $(MAKE) start; \
	fi

## clean — remove caches and temp files (keeps source, DB, .venv)
clean:
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -not -path './.venv/*' -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	@echo "Caches cleaned"

## status — show whether the bot is running
status:
	@if systemctl list-unit-files $(SERVICE).service 2>/dev/null | grep -q $(SERVICE); then \
		sudo systemctl status $(SERVICE) --no-pager || true; \
	elif [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Bot is running via nohup (PID $$(cat $(PID_FILE)))"; \
	else \
		echo "Bot is not running"; \
	fi

## logs — tail the bot log
logs:
	@mkdir -p logs
	@tail -f logs/bot.log

## install-service — install systemd service for auto-start on boot
install-service:
	@bash install-service.sh

## service-status — check systemd service status
service-status:
	@sudo systemctl status kurs-uz-bot --no-pager || true

## service-restart — restart via systemd
service-restart:
	@sudo systemctl restart kurs-uz-bot

## service-stop — stop via systemd
service-stop:
	@sudo systemctl stop kurs-uz-bot

## service-logs — follow systemd journal logs
service-logs:
	@sudo journalctl -u kurs-uz-bot -f
