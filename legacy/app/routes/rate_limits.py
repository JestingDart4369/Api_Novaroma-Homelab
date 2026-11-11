# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.deps import get_db
from app.security import get_current_user, require_admin
from app.models import User, ApiConfig, RoleLimits
from app.rate_limit import rate_limit_store

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/rate-limits", tags=["rate-limits"])

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /rate-limits/me   - your own current limit status          → any authenticated user
# GET /rate-limits/apis - status of all external API limits      → any authenticated user
# GET /rate-limits/all  - full usage breakdown (all users + apis) → admin+
#
# Auth: Required (JWT Bearer token)
# No rate limit checks on these endpoints (they're just reads)
# ============================================================

# ============================================================
# ENDPOINTS
# ============================================================

# --- My rate limit status ---
@router.get("/me")
async def get_my_rate_limits(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get limit from DB
    role_config = db.query(RoleLimits).filter(RoleLimits.role_name == user.role).first()
    limit = role_config.max_calls_per_hour if role_config else 1000

    # Peek current count without incrementing
    hour_key = rate_limit_store._get_hour_key()
    count = rate_limit_store.user_requests[user.id].get(hour_key, 0)

    return {
        "user_id":          user.id,
        "username":         user.username,
        "role":             user.role,
        "limit_per_hour":   limit,
        "used":             count,
        "remaining":        max(0, limit - count),
        "status":           "ok" if count < limit else "exceeded",
    }


# --- All API limit statuses ---
@router.get("/apis")
async def get_api_rate_limits(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    apis = db.query(ApiConfig).all()
    hour_key = rate_limit_store._get_hour_key()

    api_status = {}
    for api in apis:
        count = rate_limit_store.api_requests[api.api_name].get(hour_key, 0)
        api_status[api.api_name] = {
            "is_active":        api.is_active,
            "limit_per_hour":   api.max_calls_per_hour,
            "used":             count,
            "remaining":        max(0, api.max_calls_per_hour - count),
            "status":           "ok" if count < api.max_calls_per_hour else "exceeded",
        }

    return {"apis": api_status}


# --- Full breakdown (admin+) ---
@router.get("/all")
async def get_all_rate_limits(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hour_key = rate_limit_store._get_hour_key()

    # Per-user usage
    user_stats = {}
    for user_id, hours in rate_limit_store.user_requests.items():
        user_stats[user_id] = {
            "used_this_hour":  hours.get(hour_key, 0),
            "hourly_breakdown": dict(hours),
        }

    # Per-API usage
    apis = db.query(ApiConfig).all()
    api_stats = {}
    for api in apis:
        hours = rate_limit_store.api_requests.get(api.api_name, {})
        api_stats[api.api_name] = {
            "is_active":        api.is_active,
            "limit_per_hour":   api.max_calls_per_hour,
            "used_this_hour":   hours.get(hour_key, 0),
            "hourly_breakdown": dict(hours),
        }

    # Role limits from DB
    roles = db.query(RoleLimits).all()
    role_limits = {r.role_name: {"max_calls_per_hour": r.max_calls_per_hour, "is_active": r.is_active} for r in roles}

    return {
        "role_limits":  role_limits,
        "users":        user_stats,
        "apis":         api_stats,
    }
