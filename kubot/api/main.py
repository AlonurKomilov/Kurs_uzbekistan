from datetime import datetime
from typing import Optional, List, Literal
from decimal import Decimal
import os
import logging

# Sentry integration
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Sentry if DSN is provided
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,  # Adjust based on traffic
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    logging.info("Sentry initialized for error tracking")

# Import our core models and infrastructure
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import User, Bank, BankRate
from core.repos import UserRepository, BankRatesRepo
from infrastructure.db import get_session, init_db
from api.utils.telegram_auth import verify_init_data

app = FastAPI(title="KUBot API", version="1.0.0")

# Rate limiting middleware
from api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# CORS middleware - allow TWA dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "https://localhost:3000", 
        "https://kubot.uz",  # Production domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Bot token for HMAC verification
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Pydantic models
class UserResponse(BaseModel):
    tg_user_id: int
    lang: str

class UpdateLangRequest(BaseModel):
    lang: Literal["uz_cy", "ru", "en"]

class RateResponse(BaseModel):
    code: str
    rate: Optional[Decimal]
    fetched_at: datetime

class BankRateResponse(BaseModel):
    bank_id: int
    bank_name: str
    bank_slug: str
    code: str
    buy: Decimal
    sell: Decimal
    fetched_at: datetime

# Authentication dependency
def auth_dep(x_telegram_webapp_data: str = Header(None, alias="X-Telegram-WebApp-Data")):
    """Verify Telegram WebApp initData and return parsed auth data."""
    return verify_init_data(x_telegram_webapp_data, BOT_TOKEN)

# Dependency to get current user from Telegram WebApp data
async def get_current_user(
    auth: dict = Depends(auth_dep),
    db: AsyncSession = Depends(get_session)
) -> User:
    """Extract and verify user from Telegram WebApp initData header."""
    # Extract user data from auth dict
    user_data = auth.get('user')
    if not user_data:
        raise HTTPException(status_code=401, detail="Missing user data in initData")
    
    tg_user_id = user_data.get('id')
    if not tg_user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in initData")
    
    # Get or create user
    user_repo = UserRepository(db)
    user = await user_repo.get_or_create_user(tg_user_id)
    return user

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()

@app.get("/")
async def root():
    return {"message": "KUBot API", "version": "1.0.0"}

@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    """Enhanced health check endpoint with database connectivity and monitoring status."""
    try:
        # Check database connectivity
        result = await session.execute(select(func.count()).select_from(User))
        user_count = result.scalar()
        
        # Check if we have recent bank rates
        from datetime import timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=1)
        recent_rates = await session.execute(
            select(func.count()).select_from(BankRate)
            .where(BankRate.fetched_at > recent_cutoff)
        )
        recent_rate_count = recent_rates.scalar()
        
        return {
            "ok": True,
            "service": "api", 
            "time": datetime.utcnow().isoformat(),
            "status": "healthy",
            "database": {
                "connected": True,
                "users_count": user_count,
                "recent_rates_count": recent_rate_count
            },
            "monitoring": {
                "sentry_enabled": SENTRY_DSN is not None,
                "environment": os.getenv("ENVIRONMENT", "development")
            },
            "version": "1.0.0"
        }
    except Exception as e:
        # Report to Sentry if available
        if SENTRY_DSN:
            sentry_sdk.capture_exception(e)
        
        return {
            "ok": False,
            "service": "api",
            "time": datetime.utcnow().isoformat(), 
            "status": "unhealthy",
            "database": {
                "connected": False,
                "error": str(e)
            },
            "monitoring": {
                "sentry_enabled": SENTRY_DSN is not None,
                "environment": os.getenv("ENVIRONMENT", "development")
            },
            "version": "1.0.0"
        }

@app.get("/api/health")
async def api_health(session: AsyncSession = Depends(get_session)):
    """Detailed API health endpoint."""
    return await health(session)

@app.get("/api/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        tg_user_id=getattr(current_user, 'tg_user_id'),
        lang=getattr(current_user, 'lang')
    )

@app.post("/api/me/lang")
async def set_lang(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Update user language preference."""
    tg_id = getattr(current_user, 'tg_user_id')
    lang = payload.get("lang")
    if lang not in ("uz_cy", "ru", "en"):
        raise HTTPException(400, "unsupported lang")
    
    user_repo = UserRepository(db)
    await user_repo.update_language(tg_id, lang)
    return {"ok": True}

@app.get("/api/rates", response_model=List[RateResponse])
async def get_rates(
    codes: str = Query(..., description="Comma-separated currency codes (e.g., USD,EUR,RUB)"),
    db: AsyncSession = Depends(get_session)
):
    """Get latest CBU rates for specified currency codes."""
    # Validate and parse codes
    try:
        code_list = [code.strip().upper() for code in codes.split(',')]
        if not code_list or len(code_list) > 10:  # Limit to prevent abuse
            raise HTTPException(status_code=400, detail="Invalid codes parameter (1-10 codes allowed)")
        
        # Validate currency codes
        valid_codes = {'USD', 'EUR', 'RUB', 'GBP', 'JPY', 'CHF', 'CNY'}
        invalid_codes = set(code_list) - valid_codes
        if invalid_codes:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid currency codes: {', '.join(invalid_codes)}"
            )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid codes format")
    
    # Get latest rates from CBU (assuming bank_id=3 is CBU based on populate script)
    rates = []
    
    for code in code_list:
        # Get latest rate for this currency from CBU
        stmt = select(BankRate).where(
            and_(
                BankRate.code == code,
                BankRate.bank_id == 3  # CBU bank_id
            )
        ).order_by(desc(BankRate.fetched_at)).limit(1)
        
        result = await db.execute(stmt)
        rate_record = result.scalar_one_or_none()
        
        if rate_record:
            # For CBU rates, we'll use the sell rate as the official rate
            rates.append(RateResponse(
                code=code,
                rate=getattr(rate_record, 'sell'),
                fetched_at=getattr(rate_record, 'fetched_at')
            ))
        else:
            rates.append(RateResponse(
                code=code,
                rate=None,
                fetched_at=datetime.utcnow()
            ))
    
    return rates

@app.get("/api/bank_rates", response_model=List[BankRateResponse])
async def get_bank_rates(
    code: str = Query(..., description="Currency code (USD, EUR, RUB)"),
    limit: int = Query(10, ge=1, le=50, description="Number of results (1-50)"),
    order: Literal["sell_desc", "sell_asc", "buy_desc", "buy_asc"] = Query("sell_desc"),
    db: AsyncSession = Depends(get_session)
):
    """Get latest bank rates for a currency, ordered by sell rate."""
    # Validate currency code
    code = code.upper().strip()
    valid_codes = {'USD', 'EUR', 'RUB', 'GBP', 'JPY', 'CHF', 'CNY'}
    if code not in valid_codes:
        raise HTTPException(status_code=400, detail=f"Invalid currency code: {code}")
    
    # Parse order parameter
    order_mapping = {
        "sell_desc": desc(BankRate.sell),
        "sell_asc": BankRate.sell,
        "buy_desc": desc(BankRate.buy), 
        "buy_asc": BankRate.buy
    }
    order_clause = order_mapping[order]
    
    # Get latest rates per bank using subquery
    latest_rates_subq = select(
        BankRate.bank_id,
        func.max(BankRate.fetched_at).label('max_fetched_at')
    ).where(
        BankRate.code == code
    ).group_by(BankRate.bank_id).subquery()
    
    # Join to get the actual rate records
    stmt = select(BankRate, Bank).join(
        Bank, BankRate.bank_id == Bank.id
    ).join(
        latest_rates_subq,
        and_(
            BankRate.bank_id == latest_rates_subq.c.bank_id,
            BankRate.fetched_at == latest_rates_subq.c.max_fetched_at,
            BankRate.code == code
        )
    ).order_by(order_clause).limit(limit)
    
    result = await db.execute(stmt)
    rows = result.fetchall()
    
    rates = []
    for rate_record, bank_record in rows:
        rates.append(BankRateResponse(
            bank_id=bank_record.id,
            bank_name=bank_record.name,
            bank_slug=bank_record.slug,
            code=rate_record.code,
            buy=rate_record.buy,
            sell=rate_record.sell,
            fetched_at=rate_record.fetched_at
        ))
    
    return rates

# Legacy endpoints for backward compatibility
@app.get("/rates")
async def get_rates_legacy(db: AsyncSession = Depends(get_session)):
    """Legacy endpoint - get all rates."""
    return await get_rates(codes="USD,EUR,RUB", db=db)

@app.get("/banks")
async def get_banks(db: AsyncSession = Depends(get_session)):
    """Get all banks."""
    stmt = select(Bank).order_by(Bank.name)
    result = await db.execute(stmt)
    banks = result.scalars().all()
    
    return {
        "banks": [
            {
                "id": bank.id,
                "name": bank.name,
                "slug": bank.slug,
                "region": bank.region,
                "website": bank.website
            }
            for bank in banks
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)