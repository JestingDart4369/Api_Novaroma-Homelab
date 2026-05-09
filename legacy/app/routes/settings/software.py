# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User, Software
from app.security import require_admin, require_super_admin

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/software")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET    /settings/software         - list all software entries   → admin+
# POST   /settings/software         - register new software       → admin+
# PUT    /settings/software/{name}  - enable / disable            → superAdmin+
# DELETE /settings/software/{name}  - remove software             → superAdmin+
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class SoftwareCreate(BaseModel):
    name: str

class SoftwareUpdate(BaseModel):
    is_active: Optional[bool] = None       # device-side signal
    server_enabled: Optional[bool] = None  # server-side blocking

class SoftwareSettingsResponse(BaseModel):
    name:           str
    health:         str
    is_active:      bool   # device-side signal
    server_enabled: bool   # server-side blocking

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all registered software (admin+) ---
@router.get("")
def list_software(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = db.query(Software).order_by(Software.name).all()
    return [SoftwareSettingsResponse(name=r.name, health=r.health, is_active=r.is_active, server_enabled=r.server_enabled) for r in rows]


# --- Register new software (admin+) ---
@router.post("")
def create_software(
    body: SoftwareCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Normalise: lowercase, spaces → hyphens, strip
    name = body.name.strip().lower().replace(" ", "-")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    # Only allow URL-safe characters
    if not all(c.isalnum() or c in "-_" for c in name):
        raise HTTPException(status_code=400, detail="name may only contain letters, digits, hyphens, and underscores")

    if db.query(Software).filter(Software.name == name).first():
        raise HTTPException(status_code=409, detail=f"Software '{name}' already exists")

    row = Software(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return SoftwareSettingsResponse(name=row.name, health=row.health, is_active=row.is_active, server_enabled=row.server_enabled)


# --- Enable / disable software (superAdmin+) ---
@router.put("/{name}")
def update_software(
    name: str,
    body: SoftwareUpdate,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    row = db.query(Software).filter(Software.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Software '{name}' not found")

    if body.is_active is not None:
        row.is_active = body.is_active
    if body.server_enabled is not None:
        row.server_enabled = body.server_enabled

    db.commit()
    db.refresh(row)
    return SoftwareSettingsResponse(name=row.name, health=row.health, is_active=row.is_active, server_enabled=row.server_enabled)


# --- Remove software (superAdmin+) ---
@router.delete("/{name}")
def delete_software(
    name: str,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    row = db.query(Software).filter(Software.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Software '{name}' not found")

    db.delete(row)
    db.commit()
    return {"message": f"Software '{name}' removed"}
