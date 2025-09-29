from .main import router as main_router
from .rates import router as rates_router

def setup_handlers(dp):
    """Register all handlers."""
    dp.include_router(main_router)
    dp.include_router(rates_router)