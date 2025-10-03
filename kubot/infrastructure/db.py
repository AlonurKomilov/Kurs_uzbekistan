import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://kubot:kubot_password@localhost:5432/kubot")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    future=True,
)

# Create async session factory
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)

# Base class for models
Base = declarative_base()


def create_async_engine():
    """Create and return async database engine."""
    return engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)