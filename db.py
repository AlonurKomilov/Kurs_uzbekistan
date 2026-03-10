from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    **({} if _is_sqlite else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 5}),
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_session():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    import models  # noqa: F401 — ensure tables registered on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
