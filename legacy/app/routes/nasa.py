# ============================================================
# IMPORTS
# ============================================================
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.security import get_current_user
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/nasa", tags=["nasa"])
API_KEY = get_key("nasa")

check_nasa_limit = APIRateLimiter("nasa")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /nasa/apod                        - Astronomy Picture of the Day
# GET /nasa/epic/{collection}           - Earth satellite images (natural or enhanced)
# GET /nasa/epic/{collection}/available - list of available EPIC dates
#
# Auth: Required (JWT Bearer token)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("nasa")
#
# Response:
#   200 - Raw NASA JSON
#   400 - Invalid collection type
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config
# ============================================================

VALID_COLLECTIONS = ("natural", "enhanced")

# ============================================================
# ENDPOINTS
# ============================================================

# --- Astronomy Picture of the Day ---
@router.get("/apod")
async def get_apod(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    hd: Optional[bool] = Query(False, description="Return high-resolution image URL"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_nasa_limit),
):
    url = "https://api.nasa.gov/planetary/apod"
    params = {"api_key": API_KEY}

    if date:
        params["date"] = date
    if hd:
        params["hd"] = "true"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="NASA APOD API failed")

    return r.json()


# --- EPIC Earth satellite images ---
@router.get("/epic/{collection}")
async def get_epic(
    collection: str,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (omit for most recent)"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_nasa_limit),
):
    if collection.lower() not in VALID_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Collection must be 'natural' or 'enhanced'")

    path = f"{collection.lower()}/date/{date}" if date else collection.lower()
    url = f"https://api.nasa.gov/EPIC/api/{path}"
    params = {"api_key": API_KEY}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="NASA EPIC API failed")

    return r.json()


# --- Available EPIC dates ---
@router.get("/epic/{collection}/available")
async def get_epic_available(
    collection: str,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_nasa_limit),
):
    if collection.lower() not in VALID_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Collection must be 'natural' or 'enhanced'")

    url = f"https://api.nasa.gov/EPIC/api/{collection.lower()}/available"
    params = {"api_key": API_KEY}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="NASA EPIC API failed")

    return r.json()
