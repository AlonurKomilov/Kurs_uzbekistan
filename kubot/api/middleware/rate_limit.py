"""Rate limiting middleware for FastAPI."""
import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """
        Check if request is allowed for client.
        
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - 60  # 1 minute window
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]
        
        # Check if limit exceeded
        current_requests = len(self.requests[client_id])
        
        if current_requests >= self.requests_per_minute:
            return False, 0
        
        # Add new request
        self.requests[client_id].append(now)
        remaining = self.requests_per_minute - current_requests - 1
        
        return True, remaining
    
    def cleanup_old_entries(self, max_age_seconds: int = 300):
        """Clean up old entries to prevent memory leak."""
        now = time.time()
        cutoff = now - max_age_seconds
        
        clients_to_remove = []
        for client_id, requests in self.requests.items():
            # Remove old requests
            self.requests[client_id] = [
                req_time for req_time in requests
                if req_time > cutoff
            ]
            
            # Mark client for removal if no recent requests
            if not self.requests[client_id]:
                clients_to_remove.append(client_id)
        
        # Remove clients with no recent requests
        for client_id in clients_to_remove:
            del self.requests[client_id]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute)
        self.cleanup_counter = 0
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/health", "/"]:
            return await call_next(request)
        
        # Get client identifier (IP address or user ID from auth)
        client_id = self._get_client_id(request)
        
        # Check rate limit
        is_allowed, remaining = self.limiter.is_allowed(client_id)
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": "60"}
            )
        
        # Process request
        response: Response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        # Periodic cleanup
        self.cleanup_counter += 1
        if self.cleanup_counter >= 100:
            self.limiter.cleanup_old_entries()
            self.cleanup_counter = 0
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try to get user ID from auth header if available
        auth_header = request.headers.get("X-Telegram-WebApp-Data")
        if auth_header:
            # Use hash of auth data as identifier
            import hashlib
            return hashlib.sha256(auth_header.encode()).hexdigest()[:16]
        
        # Fallback to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        client_host = request.client.host if request.client else "unknown"
        return client_host
