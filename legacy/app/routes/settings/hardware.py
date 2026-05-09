# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User, Hardware
from app.security import require_admin, require_super_admin

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/hardware")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET    /settings/hardware         - list all hardware entries   → admin+
# POST   /settings/hardware         - register new device         → admin+
# PUT    /settings/hardware/{name}  - update config / enable      → superAdmin+
# DELETE /settings/hardware/{name}  - remove device               → superAdmin+
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class HardwareCreate(BaseModel):
    name:   str
    config: Optional[dict] = None  # initial config (optional)

class HardwareUpdate(BaseModel):
    is_active: Optional[bool] = None       # device-side signal
    server_enabled: Optional[bool] = None  # server-side blocking
    config:    Optional[dict] = None       # replace config entirely

class HardwareSettingsResponse(BaseModel):
    name:           str
    health:         str
    config:         Optional[dict] = None
    is_active:      bool   # device-side signal
    server_enabled: bool   # server-side blocking

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all registered hardware (admin+) ---
@router.get("")
def list_hardware(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = db.query(Hardware).order_by(Hardware.name).all()
    return [HardwareSettingsResponse(name=r.name, health=r.health, config=r.config, is_active=r.is_active, server_enabled=r.server_enabled) for r in rows]


# --- Register new hardware device (admin+) ---
@router.post("")
def create_hardware(
    body: HardwareCreate,
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

    if db.query(Hardware).filter(Hardware.name == name).first():
        raise HTTPException(status_code=409, detail=f"Hardware '{name}' already exists")

    row = Hardware(name=name, config=body.config)
    db.add(row)
    db.commit()
    db.refresh(row)
    return HardwareSettingsResponse(name=row.name, health=row.health, config=row.config, is_active=row.is_active, server_enabled=row.server_enabled)


# --- Update config and / or enable-disable (superAdmin+) ---
@router.put("/{name}")
def update_hardware(
    name: str,
    body: HardwareUpdate,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    row = db.query(Hardware).filter(Hardware.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Hardware '{name}' not found")

    if body.is_active is not None:
        row.is_active = body.is_active
    if body.server_enabled is not None:
        row.server_enabled = body.server_enabled
    if body.config is not None:
        row.config = body.config

    db.commit()
    db.refresh(row)
    return HardwareSettingsResponse(name=row.name, health=row.health, config=row.config, is_active=row.is_active, server_enabled=row.server_enabled)


# --- Remove hardware device (superAdmin+) ---
@router.delete("/{name}")
def delete_hardware(
    name: str,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    row = db.query(Hardware).filter(Hardware.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Hardware '{name}' not found")

    db.delete(row)
    db.commit()
    return {"message": f"Hardware '{name}' removed"}
