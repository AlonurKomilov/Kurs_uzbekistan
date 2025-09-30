import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime
from typing import Optional, List, Literal
from decimal import Decimal
import os

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import our core models and infrastructure
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import User, Bank, BankRate
from core.repos import UserRepository, BankRatesRepo
from infrastructure.db import get_session, init_db

app = FastAPI(title="FXBot API", version="1.0.0")

# CORS middleware - allow TWA dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "https://localhost:3000", 
        "https://fxbot.uz",  # Production domain
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

# HMAC verification helper
def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Verify Telegram WebApp initData using HMAC-SHA256.
    Returns parsed data if valid, raises HTTPException if invalid.
    """
    if not init_data or not bot_token:
        raise HTTPException(status_code=401, detail="Missing initData or bot token")
    
    try:
        # Parse the init data
        parsed_data = urllib.parse.parse_qs(init_data)
        
        # Extract hash and data
        received_hash = parsed_data.get('hash', [''])[0]
        if not received_hash:
            raise HTTPException(status_code=401, detail="Missing hash in initData")
        
        # Remove hash from data and sort
        data_check_arr = []
        for key, values in parsed_data.items():
            if key != 'hash':
                data_check_arr.append(f"{key}={values[0]}")
        data_check_arr.sort()
        data_check_string = '\n'.join(data_check_arr)
        
        # Create secret key: HMAC-SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            "WebAppData".encode(), 
            bot_token.encode(), 
            hashlib.sha256
        ).digest()
        
        # Calculate expected hash
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare hashes
        if not hmac.compare_digest(received_hash, expected_hash):
            raise HTTPException(status_code=401, detail="Invalid initData signature")
        
        # Parse user data
        user_data = parsed_data.get('user', [''])[0]
        if not user_data:
            raise HTTPException(status_code=401, detail="Missing user data in initData")
        
        try:
            user_info = json.loads(user_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=401, detail="Invalid user data format")
        
        return user_info
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=401, detail=f"initData verification failed: {str(e)}")

# Dependency to get current user from Telegram WebApp data
async def get_current_user(
    x_telegram_webapp_data: Optional[str] = Header(None, alias="X-Telegram-WebApp-Data"),
    db: AsyncSession = Depends(get_session)
) -> User:
    """Extract and verify user from Telegram WebApp initData header."""
    if not x_telegram_webapp_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-WebApp-Data header")
    
    user_info = verify_telegram_init_data(x_telegram_webapp_data, BOT_TOKEN)
    tg_user_id = user_info.get('id')
    
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
    return {"message": "FXBot API", "version": "1.0.0"}

@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    """Enhanced health check endpoint with database connectivity."""
    try:
        # Check database connectivity
        result = await session.execute(select(func.count()).select_from(User))
        user_count = result.scalar()
        
        # Check if we have recent bank rates
        recent_rates = await session.execute(
            select(func.count()).select_from(BankRate)
            .where(BankRate.fetched_at > func.now() - func.interval('1 hour'))
        )
        recent_rate_count = recent_rates.scalar()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "connected": True,
                "users_count": user_count,
                "recent_rates_count": recent_rate_count
            },
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "connected": False,
                "error": str(e)
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

@app.post("/api/me/lang", response_model=UserResponse)
async def update_lang(
    lang_request: UpdateLangRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Update user language preference."""
    user_repo = UserRepository(db)
    updated_user = await user_repo.update_language(getattr(current_user, 'tg_user_id'), lang_request.lang)
    
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        tg_user_id=getattr(updated_user, 'tg_user_id'),
        lang=getattr(updated_user, 'lang')
    )

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