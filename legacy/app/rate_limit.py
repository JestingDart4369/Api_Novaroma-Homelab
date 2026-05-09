# ============================================================
# IMPORTS
# ============================================================
import time
import logging
from typing import Dict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.deps import get_db
from app.security import get_current_user
from app.models import User, ApiConfig, RoleLimits

logger = logging.getLogger(__name__)

# ============================================================
# RATE LIMIT SCHEMA
# ============================================================
# Per-User Limits:
#   - Source: `role_limits` table (role_name, max_calls_per_hour, is_active)
#   - Fallback: DEFAULT_ROLE_LIMITS if role not found in DB
#   - If role is_active = false  -> 429
#   - Tracked in-memory: { user_id: { "YYYY-MM-DD-HH": count } }
#
# Per-API Limits:
#   - Source: `api_config` table (api_name, max_calls_per_hour, is_active)
#   - If api not found in DB      -> 503 (not configured)
#   - If api is_active = false    -> 503 (disabled)
#   - Tracked in-memory: { api_name: { "YYYY-MM-DD-HH": count } }
#
# Cleanup:
#   - Expired hour buckets (>2 hours old) removed every 5 minutes
#
# Response Headers (set via middleware on every response):
#   - X-RateLimit-Limit       : max requests allowed this hour (user's role limit)
#   - X-RateLimit-Remaining   : requests remaining this hour
#   - X-RateLimit-Reset       : unix timestamp when the hour resets
#   - Retry-After             : seconds until reset (only on 429)
# ============================================================

# ============================================================
# CONFIG
# ============================================================
CLEANUP_INTERVAL = 300  # 5 minutes

# Fallback per-role limits used if role_limits table has no entry for that role
from app.config import ROLE_DEFAULTS as DEFAULT_ROLE_LIMITS

# ============================================================
# RATE LIMIT STORE (IN-MEMORY)
# ============================================================
class RateLimitStore:
    """Tracks request counts per user and per API in hourly buckets."""

    def __init__(self):
        self.user_requests: Dict[int, Dict[str, int]] = defaultdict(dict)   # {user_id: {hour_key: count}}
        self.api_requests: Dict[str, Dict[str, int]] = defaultdict(dict)    # {api_name: {hour_key: count}}
        self.lock = Lock()
        self.last_cleanup = time.time()

    def _get_hour_key(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d-%H")

    def _cleanup_if_needed(self):
        now = time.time()
        if now - self.last_cleanup > CLEANUP_INTERVAL:
            self._cleanup_expired()
            self.last_cleanup = now

    def _cleanup_expired(self):
        cutoff_key = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d-%H")

        for user_id in list(self.user_requests.keys()):
            expired = [h for h in self.user_requests[user_id] if h < cutoff_key]
            for h in expired:
                del self.user_requests[user_id][h]
            if not self.user_requests[user_id]:
                del self.user_requests[user_id]

        for api_name in list(self.api_requests.keys()):
            expired = [h for h in self.api_requests[api_name] if h < cutoff_key]
            for h in expired:
                del self.api_requests[api_name][h]
            if not self.api_requests[api_name]:
                del self.api_requests[api_name]

    def check_and_increment_user(self, user_id: int, limit: int) -> Tuple[bool, int, int]:
        """Check user limit and increment if allowed. Returns (allowed, remaining, reset_timestamp)."""
        with self.lock:
            self._cleanup_if_needed()
            hour_key = self._get_hour_key()
            count = self.user_requests[user_id].get(hour_key, 0)
            next_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            reset = int(next_hour.timestamp())

            if count >= limit:
                return False, 0, reset

            self.user_requests[user_id][hour_key] = count + 1
            return True, limit - count - 1, reset

    def check_and_increment_api(self, api_name: str, limit: int) -> Tuple[bool, int, int]:
        """Check API limit and increment if allowed. Returns (allowed, remaining, reset_timestamp)."""
        with self.lock:
            self._cleanup_if_needed()
            hour_key = self._get_hour_key()
            count = self.api_requests[api_name].get(hour_key, 0)
            next_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            reset = int(next_hour.timestamp())

            if count >= limit:
                return False, 0, reset

            self.api_requests[api_name][hour_key] = count + 1
            return True, limit - count - 1, reset


# Global store — single instance shared across all requests
rate_limit_store = RateLimitStore()

# ============================================================
# USER RATE LIMIT CHECK (DEPENDENCY)
# ============================================================
async def check_user_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Checks if user has exceeded their role's hourly limit.
    Reads limit from role_limits table, falls back to DEFAULT_ROLE_LIMITS.
    Sets request.state.rate_limit_info so middleware can add response headers.
    """
    role_config = db.query(RoleLimits).filter(RoleLimits.role_name == user.role).first()

    if role_config:
        if not role_config.is_active:
            raise HTTPException(status_code=429, detail="Your role has been rate limited")
        limit = role_config.max_calls_per_hour
    else:
        # Role not in DB yet — use fallback
        limit = DEFAULT_ROLE_LIMITS.get(user.role, 1000)

    allowed, remaining, reset = rate_limit_store.check_and_increment_user(user.id, limit)

    if not allowed:
        retry_after = reset - int(time.time())
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
            }
        )

    info = {"limit": limit, "remaining": remaining, "reset": reset}
    request.state.rate_limit_info = info
    return info

# ============================================================
# API RATE LIMITER (DEPENDENCY CLASS)
# ============================================================
class APIRateLimiter:
    """
    Class-based dependency: checks if an external API has exceeded its hourly limit.
    Reads limit and active status from api_config table.
    Returns 503 if API is not configured or disabled.
    Returns 429 if API quota is exceeded.

    Usage:
        check_nasa_limit = APIRateLimiter("nasa")

        @router.get("/nasa/apod")
        async def apod(..., _api_limit: None = Depends(check_nasa_limit)):
            ...
    """

    def __init__(self, api_name: str):
        self.api_name = api_name

    async def __call__(self, db: Session = Depends(get_db)):
        api_config = db.query(ApiConfig).filter(ApiConfig.api_name == self.api_name).first()

        if not api_config or not api_config.is_active:
            raise HTTPException(status_code=503, detail=f"{self.api_name} API is currently disabled")

        limit = api_config.max_calls_per_hour
        allowed, remaining, reset = rate_limit_store.check_and_increment_api(self.api_name, limit)

        if not allowed:
            retry_after = reset - int(time.time())
            raise HTTPException(
                status_code=429,
                detail=f"API quota exceeded for {self.api_name}. Try again in {retry_after} seconds.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset),
                }
            )

# ============================================================
# MIDDLEWARE - RESPONSE HEADERS
# ============================================================
async def add_rate_limit_headers(request: Request, call_next):
    """
    HTTP middleware: adds X-RateLimit-* headers to every response.
    Reads from request.state.rate_limit_info which is set by check_user_rate_limit.
    Routes without rate limiting (e.g. /health) just won't have these headers.
    """
    response = await call_next(request)

    if hasattr(request.state, "rate_limit_info"):
        info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

    return response
