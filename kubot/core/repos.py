from typing import Optional, List, Dict
from sqlalchemy import select, update, desc, and_, insert, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from datetime import datetime, date
from core.models import User, Bank, BankRate, CbuRate, Dashboard
from infrastructure.db import SessionLocal


class UserRepository:
    """Repository for User database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_tg_user_id(self, tg_user_id: int) -> Optional[User]:
        """Get user by Telegram user ID."""
        result = await self.session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        return result.scalars().first()
    
    async def create_user(self, tg_user_id: int, lang: str = "uz_cy", tz: str = "Asia/Tashkent") -> User:
        """Create a new user."""
        user = User(tg_user_id=tg_user_id, lang=lang, tz=tz)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def update_language(self, tg_user_id: int, lang: str) -> Optional[User]:
        """Update user's language preference."""
        result = await self.session.execute(
            update(User)
            .where(User.tg_user_id == tg_user_id)
            .values(lang=lang)
            .returning(User)
        )
        user = result.scalars().first()
        if user:
            await self.session.commit()
        return user
    
    async def get_or_create_user(self, tg_user_id: int, default_lang: str = "uz_cy") -> User:
        """Get existing user or create new one."""
        user = await self.get_by_tg_user_id(tg_user_id)
        if not user:
            user = await self.create_user(tg_user_id, default_lang)
        return user
    
    async def toggle_subscription(self, tg_user_id: int) -> Optional[User]:
        """Toggle user's subscription status."""
        user = await self.get_by_tg_user_id(tg_user_id)
        if user:
            # Use update statement instead of direct attribute assignment
            new_subscribed = not bool(user.subscribed)
            await self.session.execute(
                update(User)
                .where(User.tg_user_id == tg_user_id)
                .values(subscribed=new_subscribed)
            )
            await self.session.commit()
            await self.session.refresh(user)
        return user
    
    async def get_subscribed_users(self) -> List[User]:
        """Get all subscribed users."""
        result = await self.session.execute(
            select(User).where(User.subscribed == True)
        )
        return list(result.scalars().all())
    
    async def update_subscription(self, tg_user_id: int, subscribed: bool) -> Optional[User]:
        """Update user's subscription status."""
        result = await self.session.execute(
            update(User)
            .where(User.tg_user_id == tg_user_id)
            .values(subscribed=subscribed)
            .returning(User)
        )
        user = result.scalars().first()
        if user:
            await self.session.commit()
        return user
    
    async def get_subscribers_grouped_by_lang(self) -> Dict[str, List[int]]:
        """Get subscribed users grouped by language."""
        result = await self.session.execute(
            select(User.lang, User.tg_user_id)
            .where(User.subscribed == True)
            .order_by(User.lang, User.tg_user_id)
        )
        
        groups = {}
        for lang, tg_user_id in result.all():
            if lang not in groups:
                groups[lang] = []
            groups[lang].append(tg_user_id)
        
        return groups
    
    async def soft_unsubscribe(self, tg_user_id: int) -> Optional[User]:
        """Soft unsubscribe user (blocked/unauthorized)."""
        return await self.update_subscription(tg_user_id, False)


class BankRatesRepo:
    """Repository for Bank and BankRate database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def latest_by_code(self, code: str) -> List[BankRate]:
        """Get latest rates per bank for given currency code, sorted by sell rate DESC."""
        from sqlalchemy import func
        
        # Subquery to get latest fetched_at per bank for the currency
        latest_subq = (
            select(
                BankRate.bank_id,
                func.max(BankRate.fetched_at).label('max_fetched')
            )
            .where(BankRate.code == code.upper())
            .group_by(BankRate.bank_id)
            .subquery()
        )
        
        # Main query to get the actual latest rates
        result = await self.session.execute(
            select(BankRate)
            .join(latest_subq, and_(
                BankRate.bank_id == latest_subq.c.bank_id,
                BankRate.fetched_at == latest_subq.c.max_fetched
            ))
            .where(BankRate.code == code.upper())
            .options(selectinload(BankRate.bank))
            .order_by(desc(BankRate.sell))
        )
        
        return list(result.scalars().all())
    
    async def get_bank_by_slug(self, slug: str) -> Optional[Bank]:
        """Get bank by slug."""
        result = await self.session.execute(
            select(Bank).where(Bank.slug == slug)
        )
        return result.scalars().first()
    
    async def create_bank(self, name: str, slug: str, region: str | None = None, website: str | None = None) -> Bank:
        """Create a new bank."""
        bank = Bank(name=name, slug=slug, region=region, website=website)
        self.session.add(bank)
        await self.session.commit()
        await self.session.refresh(bank)
        return bank
    
    async def add_rate(self, bank_id: int, code: str, buy: float, sell: float) -> BankRate:
        """Add a new exchange rate."""
        rate = BankRate(bank_id=bank_id, code=code.upper(), buy=buy, sell=sell)
        self.session.add(rate)
        await self.session.commit()
        await self.session.refresh(rate)
        return rate


class CbuRatesRepo:
    """Repository for CBU (Central Bank of Uzbekistan) official exchange rates."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def upsert_rate(self, code: str, rate: float, date_str: str | None = None, fetched_at: datetime | None = None):
        """Insert or update CBU rate with conflict resolution."""
        await self._upsert_in_session(self.session, code, rate, date_str, fetched_at)
    
    async def _upsert_in_session(self, session: AsyncSession, code: str, rate: float, date_str: str | None, fetched_at: datetime | None):
        """Perform upsert operation within a session."""
        try:
            # Parse date or use today
            if date_str:
                try:
                    rate_date = date.fromisoformat(date_str.split('T')[0])  # Handle datetime strings
                except (ValueError, AttributeError):
                    rate_date = date.today()
            else:
                rate_date = date.today()
            
            # Use current time if fetched_at not provided
            if fetched_at is None:
                fetched_at = datetime.utcnow()
            
            # PostgreSQL-specific upsert (INSERT ... ON CONFLICT)
            stmt = postgres_insert(CbuRate).values(
                code=code.upper(),
                rate=rate,
                rate_date=rate_date,
                fetched_at=fetched_at
            )
            
            # On conflict with code + rate_date, update rate and fetched_at
            stmt = stmt.on_conflict_do_update(
                index_elements=['code', 'rate_date'],
                set_=dict(
                    rate=stmt.excluded.rate,
                    fetched_at=stmt.excluded.fetched_at
                )
            )
            
            await session.execute(stmt)
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            raise e
    
    async def get_latest_rates(self, codes: List[str] | None = None) -> List[CbuRate]:
        """Get latest CBU rates for specified currency codes."""
        return await self._get_latest_in_session(self.session, codes)
    
    async def _get_latest_in_session(self, session: AsyncSession, codes: List[str] | None) -> List[CbuRate]:
        """Get latest rates within a session."""
        query = select(CbuRate).order_by(desc(CbuRate.rate_date), desc(CbuRate.fetched_at))
        
        if codes:
            query = query.where(CbuRate.code.in_([c.upper() for c in codes]))
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    async def get_latest_by_code(self, code: str) -> Optional[CbuRate]:
        """Get latest rate for a specific currency code."""
        return await self._get_latest_by_code_in_session(self.session, code)
    
    async def _get_latest_by_code_in_session(self, session: AsyncSession, code: str) -> Optional[CbuRate]:
        """Get latest rate for a specific currency code within a session."""
        result = await session.execute(
            select(CbuRate)
            .where(CbuRate.code == code.upper())
            .order_by(desc(CbuRate.rate_date), desc(CbuRate.fetched_at))
            .limit(1)
        )
        return result.scalars().first()
    
    async def get_by_code_and_date(self, code: str, rate_date: date) -> Optional[CbuRate]:
        """Get rate for specific currency code and date."""
        return await self._get_by_code_and_date_in_session(self.session, code, rate_date)
    
    async def _get_by_code_and_date_in_session(self, session: AsyncSession, code: str, rate_date: date) -> Optional[CbuRate]:
        """Get rate for specific currency code and date within a session."""
        result = await session.execute(
            select(CbuRate)
            .where(and_(CbuRate.code == code.upper(), CbuRate.rate_date == rate_date))
            .order_by(desc(CbuRate.fetched_at))
            .limit(1)
        )
        return result.scalars().first()


class DashboardsRepo:
    """Repository for Dashboard database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_dashboard(self, user_id: int, chat_id: int, message_id: int, initial_hash: Optional[str] = None) -> Dashboard:
        """Create a new dashboard entry."""
        dashboard = Dashboard(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            last_hash=initial_hash,
            is_active=True
        )
        self.session.add(dashboard)
        await self.session.commit()
        await self.session.refresh(dashboard)
        return dashboard
    
    async def get_by_id(self, dashboard_id: int) -> Optional[Dashboard]:
        """Get dashboard by ID."""
        result = await self.session.execute(
            select(Dashboard).where(Dashboard.id == dashboard_id)
        )
        return result.scalars().first()
    
    async def get_active_for_user(self, user_id: int, chat_id: Optional[int] = None) -> List[Dashboard]:
        """Get active dashboards for a user, optionally filtered by chat."""
        query = select(Dashboard).where(
            and_(Dashboard.user_id == user_id, Dashboard.is_active == True)
        )
        if chat_id:
            query = query.where(Dashboard.chat_id == chat_id)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_hash(self, dashboard_id: int, new_hash: str) -> bool:
        """Update the last hash for a dashboard."""
        result = await self.session.execute(
            update(Dashboard)
            .where(Dashboard.id == dashboard_id)
            .values(last_hash=new_hash, updated_at=func.now())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def replace_message_id(self, dashboard_id: int, new_message_id: int, new_hash: str) -> bool:
        """Replace message ID and hash for a dashboard (when message was deleted and recreated)."""
        result = await self.session.execute(
            update(Dashboard)
            .where(Dashboard.id == dashboard_id)
            .values(
                message_id=new_message_id,
                last_hash=new_hash,
                updated_at=func.now()
            )
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def deactivate_dashboard(self, dashboard_id: int) -> bool:
        """Deactivate a dashboard."""
        result = await self.session.execute(
            update(Dashboard)
            .where(Dashboard.id == dashboard_id)
            .values(is_active=False, updated_at=func.now())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def deactivate_user_dashboards(self, user_id: int, chat_id: Optional[int] = None) -> int:
        """Deactivate all dashboards for a user, optionally in a specific chat."""
        query = update(Dashboard).where(
            and_(Dashboard.user_id == user_id, Dashboard.is_active == True)
        )
        if chat_id:
            query = query.where(Dashboard.chat_id == chat_id)
        
        query = query.values(is_active=False, updated_at=func.now())
        
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount