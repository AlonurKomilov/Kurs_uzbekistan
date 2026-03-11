# ── KUBot Makefile ────────────────────────────────────────────────────────
PYTHON  := .venv/bin/python3
APP     := main.py
PID_FILE:= .bot.pid

.PHONY: start stop restart clean status logs

## start — launch the bot in the background
start:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Bot already running (PID $$(cat $(PID_FILE)))"; \
	else \
		nohup $(PYTHON) $(APP) >> logs/bot.log 2>&1 & echo $$! > $(PID_FILE); \
		mkdir -p logs; \
		echo "Bot started (PID $$(cat $(PID_FILE)))"; \
	fi

## stop — gracefully stop the bot
stop:
	@if [ -f $(PID_FILE) ]; then \
		PID=$$(cat $(PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID && echo "Bot stopped (PID $$PID)"; \
		else \
			echo "Bot not running (stale PID file)"; \
		fi; \
		rm -f $(PID_FILE); \
	else \
		echo "No PID file — trying to find process..."; \
		PID=$$(pgrep -f "python.*$(APP)" | head -1); \
		if [ -n "$$PID" ]; then \
			kill $$PID && echo "Bot stopped (PID $$PID)"; \
		else \
			echo "Bot is not running"; \
		fi; \
	fi

## restart — stop then start
restart: stop
	@sleep 1
	@$(MAKE) start

## clean — remove caches and temp files (keeps source, DB, .venv)
clean:
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -not -path './.venv/*' -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	@echo "Caches cleaned"

## status — show whether the bot is running
status:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Bot is running (PID $$(cat $(PID_FILE)))"; \
	else \
		PID=$$(pgrep -f "python.*$(APP)" | head -1); \
		if [ -n "$$PID" ]; then \
			echo "Bot is running (PID $$PID, no PID file)"; \
		else \
			echo "Bot is not running"; \
		fi; \
	fi

## logs — tail the bot log
logs:
	@mkdir -p logs
	@tail -f logs/bot.log
