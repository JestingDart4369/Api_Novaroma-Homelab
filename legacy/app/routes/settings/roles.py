# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User, RoleLimits
from app.security import require_admin, require_root

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/roles")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET /settings/roles            - list all role limits          → admin, superAdmin, Root
# PUT /settings/roles/{role_name} - update max_calls / active    → Root only
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class RoleLimitResponse(BaseModel):
    role_name: str
    max_calls_per_hour: int
    is_active: bool

class RoleLimitUpdate(BaseModel):
    max_calls_per_hour: Optional[int] = None
    is_active: Optional[bool] = None

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all role limits (admin+) ---
@router.get("")
def list_roles(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    roles = db.query(RoleLimits).all()
    return [RoleLimitResponse(role_name=r.role_name, max_calls_per_hour=r.max_calls_per_hour, is_active=r.is_active) for r in roles]


# --- Update role limits (Root only) ---
@router.put("/{role_name}")
def update_role(
    role_name: str,
    body: RoleLimitUpdate,
    db: Session = Depends(get_db),
    root: User = Depends(require_root),
):
    valid_roles = ("user", "admin", "superAdmin", "Root")
    if role_name not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    role = db.query(RoleLimits).filter(RoleLimits.role_name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

    if body.max_calls_per_hour is not None:
        if body.max_calls_per_hour < 1:
            raise HTTPException(status_code=400, detail="max_calls_per_hour must be at least 1")
        role.max_calls_per_hour = body.max_calls_per_hour

    if body.is_active is not None:
        role.is_active = body.is_active

    db.commit()
    db.refresh(role)
    return RoleLimitResponse(role_name=role.role_name, max_calls_per_hour=role.max_calls_per_hour, is_active=role.is_active)
