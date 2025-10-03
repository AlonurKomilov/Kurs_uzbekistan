# api/utils/telegram_auth.py
import hmac
import hashlib
import urllib.parse
import json
from fastapi import HTTPException


def verify_init_data(init_data: str, bot_token: str):
    """
    Verify Telegram WebApp initData using HMAC-SHA256.
    Returns parsed user data if valid, raises HTTPException if invalid.
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    
    if not bot_token:
        raise HTTPException(status_code=401, detail="Missing bot token")
    
    try:
        # Parse into dict - parse_qsl preserves order better than parse_qs
        pairs = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        
        # Extract and remove hash
        hash_recv = pairs.pop("hash", None)
        if not hash_recv:
            raise HTTPException(status_code=401, detail="Missing hash in initData")
        
        # Create data check string
        data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
        
        # Create secret key: HMAC-SHA256("WebAppData", bot_token)
        secret = hmac.new(
            "WebAppData".encode(),
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # Calculate expected hash
        expected_hash = hmac.new(
            secret,
            data_check.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare hashes
        if not hmac.compare_digest(expected_hash, hash_recv):
            raise HTTPException(status_code=401, detail="Invalid initData")
        
        # Parse user data if present
        user_data_str = pairs.get("user")
        if user_data_str:
            try:
                user_data = json.loads(user_data_str)
                pairs["user"] = user_data
            except json.JSONDecodeError:
                raise HTTPException(status_code=401, detail="Invalid user data format")
        
        return pairs  # contains user data, auth_date, etc.
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"initData verification failed: {str(e)}")