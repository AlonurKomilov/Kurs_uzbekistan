"""Combined database + i18n middleware."""

from __future__ import annotations

import os
import re
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import User

from db import SessionLocal
from repos import BankRatesRepo, UserRepo


class DbMiddleware(BaseMiddleware):
    """Injects db_session, user_repo, bank_rates_repo, db_user, user_lang."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            data["db_session"] = session
            data["user_repo"] = UserRepo(session)
            data["bank_rates_repo"] = BankRatesRepo(session)

            tg_user = _extract_user(event)
            if tg_user:
                repo = data["user_repo"]
                db_user = await repo.get_or_create(tg_user.id)
                data["db_user"] = db_user
                data["user_lang"] = db_user.lang

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class I18nMiddleware(BaseMiddleware):
    """Simple .ftl-based i18n. Injects `i18n` callable and `locale` string."""

    SUPPORTED = ("uz_cy", "ru", "en")
    DEFAULT = "uz_cy"

    def __init__(self):
        self.messages: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
        for loc in self.SUPPORTED:
            path = os.path.join(base, loc, "messages.ftl")
            if os.path.exists(path):
                self.messages[loc] = _parse_ftl(path)

    def get_text(self, locale: str, key: str, **kwargs) -> str:
        msgs = self.messages.get(locale, self.messages.get(self.DEFAULT, {}))
        text = msgs.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        tg_user = _extract_user(event)
        user_lang = data.get("user_lang")
        locale = self._resolve_locale(tg_user, user_lang)
        data["i18n"] = lambda key, **kw: self.get_text(locale, key, **kw)
        data["locale"] = locale
        return await handler(event, data)

    def _resolve_locale(self, tg_user: User | None, db_lang: str | None) -> str:
        if db_lang and db_lang in self.SUPPORTED:
            return db_lang
        if tg_user and tg_user.language_code:
            mapping = {"uz": "uz_cy", "ru": "ru", "en": "en"}
            mapped = mapping.get(tg_user.language_code.lower())
            if mapped:
                return mapped
        return self.DEFAULT


def _extract_user(event: Any) -> User | None:
    for attr in ("from_user", "message", "callback_query", "inline_query"):
        obj = getattr(event, attr, None)
        if obj is None:
            continue
        if isinstance(obj, User):
            return obj
        u = getattr(obj, "from_user", None)
        if isinstance(u, User):
            return u
    return None


def _parse_ftl(path: str) -> dict[str, str]:
    msgs: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                value = re.sub(r"\{ \$(\w+) \}", r"{\1}", value)
                msgs[key] = value
    return msgs
