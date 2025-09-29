import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.db import get_session, init_db

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="FXBot API",
    description="Currency exchange bot API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "FXBot API is running"}


@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check endpoint."""
    return {"status": "healthy", "database": "connected"}


@app.get("/rates")
async def get_rates(session: AsyncSession = Depends(get_session)):
    """Get currency rates."""
    # Placeholder for actual implementation
    return {"rates": {"USD": 1.0, "EUR": 0.85, "UZS": 12000}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)