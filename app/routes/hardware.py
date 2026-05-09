# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User, Hardware
from app.security import get_current_user

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/hardware", tags=["hardware"])

STALE_THRESHOLD_MINUTES = 5

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET  /hardware                  - list all registered hardware   → any authenticated user
# GET  /hardware/{name}           - get health + config for one    → any authenticated user
# POST /hardware/{name}/heartbeat - device pushes its status       → any authenticated user
#
# Auth: JWT Bearer token required on all endpoints
#
# Response fields:
#   name            - registered device name (URL slug)
#   health          - "ok" | "warning" | "error" | "killed" | "unknown"
#   last_heartbeat  - ISO timestamp of last push, or null
#   stale           - true if no heartbeat in the last 5 minutes
#   config          - free-form JSON with device config (set via heartbeat or /settings/hardware)
#   details         - free-form JSON with runtime health details (set via heartbeat)
#   is_active       - whether this hardware entry is enabled
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class HeartbeatBody(BaseModel):
    health:  str                    # "ok", "warning", "error", "killed"
    config:  Optional[dict] = None  # device config (optional — only sent when it changes)
    details: Optional[dict] = None  # runtime health details

# ============================================================
# HELPERS
# ============================================================
def _is_stale(last_heartbeat: Optional[datetime]) -> bool:
    if last_heartbeat is None:
        return True
    now = datetime.now(timezone.utc)
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
    return (now - last_heartbeat).total_seconds() > STALE_THRESHOLD_MINUTES * 60


def _format(row: Hardware) -> dict:
    return {
        "name":           row.name,
        "health":         row.health,
        "last_heartbeat": row.last_heartbeat.isoformat() if row.last_heartbeat else None,
        "stale":          _is_stale(row.last_heartbeat),
        "config":         row.config,
        "details":        row.details,
        "is_active":      row.is_active,        # device-side signal
        "server_enabled": row.server_enabled,   # server-side blocking
    }

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all hardware ---
@router.get("")
def list_hardware(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Hardware).order_by(Hardware.name).all()
    return [_format(r) for r in rows]


# --- Get one hardware by name ---
@router.get("/{name}")
def get_hardware(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.query(Hardware).filter(Hardware.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Hardware '{name}' not found")
    if not row.server_enabled:
        raise HTTPException(status_code=503, detail=f"Hardware '{name}' is disabled server-side")
    return _format(row)


# --- Hardware device pushes its own status + optional config ---
@router.post("/{name}/heartbeat")
def push_heartbeat(
    name: str,
    body: HeartbeatBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.health not in ("ok", "warning", "error", "killed"):
        raise HTTPException(status_code=400, detail='health must be "ok", "warning", "error", or "killed"')

    row = db.query(Hardware).filter(Hardware.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Hardware '{name}' not registered — add it via /settings/hardware first")
    if not row.server_enabled:
        raise HTTPException(status_code=503, detail=f"Hardware '{name}' is disabled server-side")

    row.health         = body.health
    row.last_heartbeat = datetime.now(timezone.utc)
    if body.config is not None:
        row.config = body.config
    if body.details is not None:
        row.details = body.details

    db.commit()
    db.refresh(row)
    return _format(row)
