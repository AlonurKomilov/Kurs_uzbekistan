from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Alert, Bank, BankRate, ChannelSub, User


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

    async def previous_by_code(self, code: str) -> dict[int, BankRate]:
        """Second-latest rate per bank for given currency. Returns {bank_id: BankRate}."""
        # Subquery: max fetched_at per bank (the latest)
        latest_sub = (
            select(BankRate.bank_id, func.max(BankRate.fetched_at).label("mf"))
            .where(BankRate.code == code.upper())
            .group_by(BankRate.bank_id)
            .subquery()
        )
        # Subquery: max fetched_at per bank EXCLUDING the latest
        prev_sub = (
            select(
                BankRate.bank_id,
                func.max(BankRate.fetched_at).label("pf"),
            )
            .join(latest_sub, BankRate.bank_id == latest_sub.c.bank_id)
            .where(
                BankRate.code == code.upper(),
                BankRate.fetched_at < latest_sub.c.mf,
            )
            .group_by(BankRate.bank_id)
            .subquery()
        )
        result = await self.s.execute(
            select(BankRate)
            .join(prev_sub, and_(
                BankRate.bank_id == prev_sub.c.bank_id,
                BankRate.fetched_at == prev_sub.c.pf,
            ))
            .where(BankRate.code == code.upper())
        )
        return {r.bank_id: r for r in result.scalars().all()}

    async def get_cbu_rate(self, code: str) -> Optional[BankRate]:
        """Get the latest CBU rate for a currency."""
        result = await self.s.execute(
            select(BankRate)
            .join(Bank)
            .where(Bank.slug == "cbu", BankRate.code == code.upper())
            .order_by(desc(BankRate.fetched_at))
            .limit(1)
        )
        return result.scalars().first()

    async def delete_older_than(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.s.execute(
            delete(BankRate).where(BankRate.fetched_at < cutoff)
        )
        return result.rowcount  # type: ignore[return-value]

    async def count_rates(self) -> int:
        result = await self.s.execute(select(func.count(BankRate.id)))
        return result.scalar() or 0

    async def count_banks(self) -> int:
        result = await self.s.execute(select(func.count(Bank.id)))
        return result.scalar() or 0

    async def last_collection_time(self) -> Optional[datetime]:
        result = await self.s.execute(select(func.max(BankRate.fetched_at)))
        return result.scalar()


class StatsRepo:
    """Read-only statistics queries for admin panel."""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def count_users(self) -> int:
        result = await self.s.execute(select(func.count(User.id)))
        return result.scalar() or 0

    async def count_subscribers(self) -> int:
        result = await self.s.execute(
            select(func.count(User.id)).where(User.subscribed.is_(True))
        )
        return result.scalar() or 0

    async def subscribers_by_schedule(self) -> dict[str, int]:
        result = await self.s.execute(
            select(User.digest_schedule, func.count(User.id))
            .where(User.subscribed.is_(True))
            .group_by(User.digest_schedule)
        )
        return dict(result.all())

    async def new_users(self, days: int = 7) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.s.execute(
            select(func.count(User.id)).where(User.created_at >= cutoff)
        )
        return result.scalar() or 0


class AlertRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, tg_user_id: int, code: str, direction: str, threshold: float) -> Alert:
        alert = Alert(
            tg_user_id=tg_user_id, code=code.upper(),
            direction=direction, threshold=threshold,
        )
        self.s.add(alert)
        await self.s.flush()
        return alert

    async def list_active(self, tg_user_id: int) -> list[Alert]:
        result = await self.s.execute(
            select(Alert)
            .where(Alert.tg_user_id == tg_user_id, Alert.triggered.is_(False))
            .order_by(Alert.created_at)
        )
        return list(result.scalars().all())

    async def delete_by_id(self, alert_id: int, tg_user_id: int) -> bool:
        result = await self.s.execute(
            delete(Alert).where(Alert.id == alert_id, Alert.tg_user_id == tg_user_id)
        )
        return (result.rowcount or 0) > 0

    async def get_pending(self) -> list[Alert]:
        """All non-triggered alerts."""
        result = await self.s.execute(
            select(Alert).where(Alert.triggered.is_(False))
        )
        return list(result.scalars().all())

    async def mark_triggered(self, alert_id: int) -> None:
        await self.s.execute(
            update(Alert).where(Alert.id == alert_id).values(triggered=True)
        )

    async def history_for_chart(self, code: str, days: int = 7) -> list[tuple[datetime, float, float]]:
        """Best sell + best buy per day for chart. Returns (date, max_sell, max_buy)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.s.execute(
            select(
                func.date(BankRate.fetched_at).label("day"),
                func.max(BankRate.sell).label("best_sell"),
                func.max(BankRate.buy).label("best_buy"),
            )
            .where(BankRate.code == code.upper(), BankRate.fetched_at >= cutoff)
            .group_by(func.date(BankRate.fetched_at))
            .order_by(func.date(BankRate.fetched_at))
        )
        rows = result.all()
        parsed = []
        for row in rows:
            day = row.day
            if isinstance(day, str):
                day = datetime.strptime(day, "%Y-%m-%d").date()
            parsed.append((day, float(row.best_sell), float(row.best_buy)))
        return parsed


class ChannelSubRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_or_create(
        self, chat_id: int, title: str, added_by: int
    ) -> ChannelSub:
        result = await self.s.execute(
            select(ChannelSub).where(ChannelSub.chat_id == chat_id)
        )
        sub = result.scalars().first()
        if not sub:
            sub = ChannelSub(chat_id=chat_id, title=title, added_by=added_by)
            self.s.add(sub)
            await self.s.flush()
        return sub

    async def set_schedule(self, chat_id: int, schedule: str) -> None:
        await self.s.execute(
            update(ChannelSub)
            .where(ChannelSub.chat_id == chat_id)
            .values(schedule=schedule)
        )

    async def set_lang(self, chat_id: int, lang: str) -> None:
        await self.s.execute(
            update(ChannelSub)
            .where(ChannelSub.chat_id == chat_id)
            .values(lang=lang)
        )

    async def remove(self, chat_id: int) -> bool:
        result = await self.s.execute(
            delete(ChannelSub).where(ChannelSub.chat_id == chat_id)
        )
        return (result.rowcount or 0) > 0

    async def get_by_schedule(self, schedule: str) -> list[ChannelSub]:
        """Get channels for a specific schedule (morning/evening)."""
        if schedule == "twice":
            result = await self.s.execute(select(ChannelSub))
        else:
            result = await self.s.execute(
                select(ChannelSub).where(
                    (ChannelSub.schedule == schedule)
                    | (ChannelSub.schedule == "twice")
                )
            )
        return list(result.scalars().all())

    async def get_by_chat_id(self, chat_id: int) -> ChannelSub | None:
        result = await self.s.execute(
            select(ChannelSub).where(ChannelSub.chat_id == chat_id)
        )
        return result.scalars().first()
