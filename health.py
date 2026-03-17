"""Lightweight /health HTTP endpoint for monitoring."""

from __future__ import annotations

import json
import logging
from aiohttp import web

from config import settings

logger = logging.getLogger(__name__)


async def _health_handler(request: web.Request) -> web.Response:
    import collector_stats

    runs = collector_stats.get_all()
    ok_count = sum(1 for r in runs.values() if r.success)
    total = len(runs)

    body = {
        "status": "ok",
        "uptime_s": round(collector_stats.uptime_seconds()),
        "collectors": {"ok": ok_count, "total": total},
    }
    return web.json_response(body)


async def start_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", _health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.HEALTH_PORT)
    await site.start()
    logger.info("Health server listening on :%d", settings.HEALTH_PORT)
    return runner
