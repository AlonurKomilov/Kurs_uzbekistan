"""Pytest configuration and fixtures."""
import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set test environment variables
os.environ["DATABASE_URL"] = "postgresql+asyncpg://kubot:kubot_password@localhost:5432/kubot_test"
os.environ["BOT_TOKEN"] = "test_bot_token_123456"
os.environ["SQL_DEBUG"] = "false"

from infrastructure.db import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False,
        pool_pre_ping=True,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    SessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "tg_user_id": 123456789,
        "lang": "en",
        "tz": "Asia/Tashkent",
        "subscribed": False,
    }


@pytest.fixture
def sample_bank_data():
    """Sample bank data for testing."""
    return {
        "name": "Test Bank",
        "slug": "test_bank",
        "region": "Uzbekistan",
        "website": "https://testbank.uz",
    }


@pytest.fixture
def sample_rate_data():
    """Sample rate data for testing."""
    return {
        "code": "USD",
        "buy": 12500.0,
        "sell": 12550.0,
    }
