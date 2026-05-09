# ============================================================
# IMPORTS
# ============================================================
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from typing import Optional
from app.security import get_current_user
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/telephone", tags=["telephone"])
API_KEY = get_key("telephone")

check_telephone_limit = APIRateLimiter("telephone")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /telephone/search - search Swiss telephone directory (search.ch)
#
# Auth: Required (JWT Bearer token)
#
# Query Params:
#   was     (str, required)   - Search term: name, category, or phone number
#   wo      (str, optional)   - Location: street, city, postal code, or canton
#   privat  (int, optional)   - Include private entries (1=yes, 0=no, default: 1)
#   firma   (int, optional)   - Include business entries (1=yes, 0=no, default: 1)
#   pos     (int, optional)   - Starting position for pagination
#   maxnum  (int, optional)   - Results per page (max 200)
#   lang    (str, optional)   - Language: de, fr, it, en (default: en)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("telephone")
#
# Response:
#   200 - XML (Atom Feed) from search.ch
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config
# ============================================================

# ============================================================
# ENDPOINTS
# ============================================================
@router.get("/search")
async def telephone_search(
    was: str = Query(..., description="Search term: name, category, or phone number"),
    wo: Optional[str] = Query(None, description="Location: street, city, postal code, or canton"),
    privat: Optional[int] = Query(1, description="Include private entries (1=yes, 0=no)"),
    firma: Optional[int] = Query(1, description="Include business entries (1=yes, 0=no)"),
    pos: Optional[int] = Query(None, description="Starting position for pagination"),
    maxnum: Optional[int] = Query(None, description="Results per page (max 200)"),
    lang: Optional[str] = Query("en", description="Language: de, fr, it, en"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_telephone_limit),
):
    url = "https://search.ch/tel/api/"
    params = {
        "was": was,
        "key": API_KEY,
        "lang": lang,
        "privat": privat,
        "firma": firma,
    }

    if wo:
        params["wo"] = wo
    if pos is not None:
        params["pos"] = pos
    if maxnum is not None:
        params["maxnum"] = min(maxnum, 200)

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code == 403:
        raise HTTPException(status_code=502, detail="Telephone API authorization failed")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream telephone API failed")

    return Response(content=r.content, media_type="application/xml")
