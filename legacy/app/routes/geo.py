# ============================================================
# IMPORTS
# ============================================================
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from app.security import get_current_user
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/geo", tags=["geo"])
GEOAPIFY_KEY = get_key("geoapify")
IPREGISTRY_KEY = get_key("ipregistry")

check_geoapify_limit = APIRateLimiter("geoapify")
check_ipregistry_limit = APIRateLimiter("ipregistry")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /geo/geocode  - geocode a place name to coordinates (Geoapify)
# GET /geo/ip       - get location from IP address (IPRegistry)
#
# Auth: Required (JWT Bearer token)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - /geo/geocode uses api_config "geoapify"
#   - /geo/ip      uses api_config "ipregistry"
#
# Response:
#   200 - Raw upstream JSON
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config
# ============================================================

# ============================================================
# ENDPOINTS
# ============================================================

# --- Geocode place name to coordinates ---
@router.get("/geocode")
async def geocode(
    text: str = Query(..., description="Place name to geocode"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_geoapify_limit),
):
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {"text": text, "apiKey": GEOAPIFY_KEY}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream geocode API failed")

    return r.json()


# --- Get location from IP address ---
@router.get("/ip")
async def get_location_from_ip(
    ip: str = Query(None, description="IP address to look up (omit to use your own)"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_ipregistry_limit),
):
    url = f"https://api.ipregistry.co/{ip}" if ip else "https://api.ipregistry.co"
    params = {"key": IPREGISTRY_KEY, "fields": "location.city,connection"}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream IP geolocation API failed")

    return r.json()
