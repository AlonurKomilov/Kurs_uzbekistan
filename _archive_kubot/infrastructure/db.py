import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Database URL from environment — required, no default
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",  # Controlled by environment
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=20,  # Adjust based on load
    max_overflow=10,  # Additional connections if pool exhausted
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


def get_engine():
    """Get the database engine instance."""
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


@asynccontextmanager
async def get_session_context():
    """Async context manager for database sessions (use outside FastAPI DI)."""
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