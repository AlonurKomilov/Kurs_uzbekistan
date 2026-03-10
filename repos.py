from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Bank, BankRate, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_or_create(self, tg_user_id: int, default_lang: str = "uz_cy") -> User:
        result = await self.s.execute(select(User).where(User.tg_user_id == tg_user_id))
        user = result.scalars().first()
        if not user:
            user = User(tg_user_id=tg_user_id, lang=default_lang)
            self.s.add(user)
            await self.s.flush()
        return user

    async def update_language(self, tg_user_id: int, lang: str) -> None:
        await self.s.execute(
            update(User).where(User.tg_user_id == tg_user_id).values(lang=lang)
        )

    async def toggle_subscription(self, tg_user_id: int) -> User:
        result = await self.s.execute(select(User).where(User.tg_user_id == tg_user_id))
        user = result.scalars().first()
        if user:
            await self.s.execute(
                update(User)
                .where(User.tg_user_id == tg_user_id)
                .values(subscribed=not bool(user.subscribed))
            )
            await self.s.refresh(user)
        return user  # type: ignore[return-value]

    async def set_digest_schedule(
        self, tg_user_id: int, schedule: str, custom_time=None
    ) -> None:
        values: dict = {"digest_schedule": schedule}
        if custom_time is not None:
            values["digest_time"] = custom_time
        await self.s.execute(
            update(User).where(User.tg_user_id == tg_user_id).values(**values)
        )

    async def get_subscribers_by_schedule(self, schedule: str) -> dict[str, list[int]]:
        result = await self.s.execute(
            select(User.lang, User.tg_user_id)
            .where(User.subscribed.is_(True), User.digest_schedule == schedule)
            .order_by(User.lang)
        )
        groups: dict[str, list[int]] = {}
        for lang, tid in result.all():
            groups.setdefault(lang, []).append(tid)
        return groups

    async def get_all_subscribers_grouped(self) -> dict[str, list[int]]:
        result = await self.s.execute(
            select(User.lang, User.tg_user_id)
            .where(User.subscribed.is_(True))
            .order_by(User.lang)
        )
        groups: dict[str, list[int]] = {}
        for lang, tid in result.all():
            groups.setdefault(lang, []).append(tid)
        return groups

    async def soft_unsubscribe(self, tg_user_id: int) -> None:
        await self.s.execute(
            update(User).where(User.tg_user_id == tg_user_id).values(subscribed=False)
        )


class BankRatesRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_bank_by_slug(self, slug: str) -> Optional[Bank]:
        result = await self.s.execute(select(Bank).where(Bank.slug == slug))
        return result.scalars().first()

    async def add_rate(self, bank_id: int, code: str, buy: float, sell: float) -> BankRate:
        rate = BankRate(bank_id=bank_id, code=code.upper(), buy=buy, sell=sell)
        self.s.add(rate)
        await self.s.flush()
        return rate

    async def latest_by_code(self, code: str) -> list[BankRate]:
        """Latest rate per bank for given currency, sorted by sell DESC."""
        sub = (
            select(BankRate.bank_id, func.max(BankRate.fetched_at).label("mf"))
            .where(BankRate.code == code.upper())
            .group_by(BankRate.bank_id)
            .subquery()
        )
        result = await self.s.execute(
            select(BankRate)
            .join(sub, and_(BankRate.bank_id == sub.c.bank_id, BankRate.fetched_at == sub.c.mf))
            .where(BankRate.code == code.upper())
            .options(selectinload(BankRate.bank))
            .order_by(desc(BankRate.sell))
        )
        return list(result.scalars().all())

    async def delete_older_than(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.s.execute(
            delete(BankRate).where(BankRate.fetched_at < cutoff)
        )
        return result.rowcount  # type: ignore[return-value]
