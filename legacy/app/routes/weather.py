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
router = APIRouter(prefix="/weather", tags=["weather"])
API_KEY = get_key("openweather")

check_openweather_limit = APIRateLimiter("openweather")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /weather                  - current weather by city
# GET /weather/forecast/hourly  - 48h hourly forecast by lat/lon
# GET /weather/forecast/daily   - up to 16-day daily forecast by lat/lon
#
# All use OpenWeather API (shared "openweather" rate limit)
# Auth: Required (JWT Bearer token)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("openweather")
#
# Response:
#   200 - Raw OpenWeather JSON
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config
# ============================================================

# ============================================================
# ENDPOINTS
# ============================================================

# --- Current weather ---
@router.get("")
async def get_weather(
    city: str = Query(..., description="City name"),
    units: str = Query("metric", description="Units: metric, imperial, standard"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_openweather_limit),
):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": API_KEY, "units": units}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream weather API failed")

    return r.json()


# --- Hourly forecast (next 48 hours) ---
@router.get("/forecast/hourly")
async def get_hourly_forecast(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    units: str = Query("metric", description="Units: metric, imperial, standard"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_openweather_limit),
):
    url = "https://pro.openweathermap.org/data/2.5/forecast/hourly"
    params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": units}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream forecast API failed")

    return r.json()


# --- Daily forecast (up to 16 days) ---
@router.get("/forecast/daily")
async def get_daily_forecast(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    cnt: int = Query(7, description="Number of days (1-16)"),
    units: str = Query("metric", description="Units: metric, imperial, standard"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_openweather_limit),
):
    url = "https://api.openweathermap.org/data/2.5/forecast/daily"
    params = {"lat": lat, "lon": lon, "cnt": min(cnt, 16), "appid": API_KEY, "units": units}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream forecast API failed")

    return r.json()
