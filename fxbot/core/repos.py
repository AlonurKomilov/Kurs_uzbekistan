from typing import Optional, List
from sqlalchemy import select, update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from core.models import User, Bank, BankRate


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