import os
import logging
from typing import Optional, Tuple
import jwt
from fastapi import HTTPException, Header
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

JWT_PUBLIC_KEY_URL = "https://codingafterdark.de/authentication/public-key"
ADMIN_ID = os.getenv("ADMIN_DISCORD_ID")

# Cache with TTL
_public_key_cache: Optional[str] = None
_cache_timestamp: Optional[datetime] = None
_CACHE_TTL = timedelta(minutes=10)


def get_public_key() -> str:
    """
    Fetch and cache the public key from the auth service.
    Cache is refreshed every hour to account for key rotation.
    """
    global _public_key_cache, _cache_timestamp
    
    if _public_key_cache and _cache_timestamp:
        if datetime.utcnow() - _cache_timestamp < _CACHE_TTL:
            return _public_key_cache
    
    try:
        response = requests.get(JWT_PUBLIC_KEY_URL, timeout=5)
        response.raise_for_status()
        
        # Extract public key from response
        data = response.json()
        public_key = data.get("public_key")
        
        if not public_key:
            raise ValueError("No public_key in response")
        
        _public_key_cache = public_key
        _cache_timestamp = datetime.utcnow()
        logger.info("Public key fetched and cached from auth service")
        return public_key
    
    except Exception as e:
        logger.error(f"Failed to fetch public key from {JWT_PUBLIC_KEY_URL}: {e}")
        if _public_key_cache:
            logger.warning("Using cached public key due to fetch error")
            return _public_key_cache
        raise


async def verify_jwt(authorization: str = Header(...)) -> dict:
    """
    Verify JWT token and return payload.
    
    Args:
        authorization: Bearer token from Authorization header
        
    Returns:
        JWT payload dict with userId, discordId, roles, etc.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    
    token = authorization[7:]
    
    try:
        public_key = get_public_key()
        payload = jwt.decode(token, public_key, algorithms=["RS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(status_code=500, detail="Token verification failed")


async def require_admin(payload: dict = None) -> dict:
    """
    Verify that user is admin.
    
    Args:
        payload: JWT payload from verify_jwt
        
    Returns:
        JWT payload if admin
    """
    if not payload:
        raise HTTPException(status_code=403, detail="Missing token")
    
    discord_id = payload.get("discordId")
    
    if discord_id != ADMIN_ID:
        logger.warning(f"Unauthorized admin access attempt from {discord_id}")
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return payload
