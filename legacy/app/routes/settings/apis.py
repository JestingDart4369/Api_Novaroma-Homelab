# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User, ApiConfig
from app.security import require_admin, require_super_admin

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/apis")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /settings/apis            - list all API configs          → admin, superAdmin, Root
# GET /settings/apis/{api_name} - get single API config         → admin, superAdmin, Root
# PUT /settings/apis/{api_name} - update enabled / max_calls    → superAdmin, Root
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class ApiConfigResponse(BaseModel):
    api_name: str
    is_active: bool
    max_calls_per_hour: int

class ApiConfigUpdate(BaseModel):
    is_active: Optional[bool] = None
    max_calls_per_hour: Optional[int] = None

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all API configs (admin+) ---
@router.get("")
def list_apis(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    apis = db.query(ApiConfig).all()
    return [ApiConfigResponse(api_name=a.api_name, is_active=a.is_active, max_calls_per_hour=a.max_calls_per_hour) for a in apis]


# --- Get single API config (admin+) ---
@router.get("/{api_name}")
def get_api(
    api_name: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    api = db.query(ApiConfig).filter(ApiConfig.api_name == api_name).first()
    if not api:
        raise HTTPException(status_code=404, detail=f"API '{api_name}' not found")
    return ApiConfigResponse(api_name=api.api_name, is_active=api.is_active, max_calls_per_hour=api.max_calls_per_hour)


# --- Update API config (superAdmin+) ---
@router.put("/{api_name}")
def update_api(
    api_name: str,
    body: ApiConfigUpdate,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    api = db.query(ApiConfig).filter(ApiConfig.api_name == api_name).first()
    if not api:
        raise HTTPException(status_code=404, detail=f"API '{api_name}' not found")

    if body.is_active is not None:
        api.is_active = body.is_active

    if body.max_calls_per_hour is not None:
        if body.max_calls_per_hour < 1:
            raise HTTPException(status_code=400, detail="max_calls_per_hour must be at least 1")
        api.max_calls_per_hour = body.max_calls_per_hour

    db.commit()
    db.refresh(api)
    return ApiConfigResponse(api_name=api.api_name, is_active=api.is_active, max_calls_per_hour=api.max_calls_per_hour)
