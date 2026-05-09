# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User, Software
from app.security import get_current_user

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/software", tags=["software"])

STALE_THRESHOLD_MINUTES = 5

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET  /software                  - list all registered software   → any authenticated user
# GET  /software/{name}           - get health status for one      → any authenticated user
# POST /software/{name}/heartbeat - software pushes its status     → any authenticated user
#
# Auth: JWT Bearer token required on all endpoints
#
# Response fields:
#   name            - registered software name (URL slug)
#   health          - "ok" | "warning" | "error" | "killed" | "unknown"
#   last_heartbeat  - ISO timestamp of last push, or null
#   stale           - true if no heartbeat in the last 5 minutes
#   details         - free-form JSON sent by the software on heartbeat
#   is_active       - whether this software entry is enabled
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class HeartbeatBody(BaseModel):
    health: str                    # "ok", "warning", "error", "killed"
    details: Optional[dict] = None # optional extra info

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


def _format(row: Software) -> dict:
    return {
        "name":           row.name,
        "health":         row.health,
        "last_heartbeat": row.last_heartbeat.isoformat() if row.last_heartbeat else None,
        "stale":          _is_stale(row.last_heartbeat),
        "details":        row.details,
        "is_active":      row.is_active,        # device-side signal
        "server_enabled": row.server_enabled,   # server-side blocking
    }

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all software ---
@router.get("")
def list_software(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Software).order_by(Software.name).all()
    return [_format(r) for r in rows]


# --- Get one software by name ---
@router.get("/{name}")
def get_software(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.query(Software).filter(Software.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Software '{name}' not found")
    if not row.server_enabled:
        raise HTTPException(status_code=503, detail=f"Software '{name}' is disabled server-side")
    return _format(row)


# --- Software pushes its own health status ---
@router.post("/{name}/heartbeat")
def push_heartbeat(
    name: str,
    body: HeartbeatBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.health not in ("ok", "warning", "error", "killed"):
        raise HTTPException(status_code=400, detail='health must be "ok", "warning", "error", or "killed"')

    row = db.query(Software).filter(Software.name == name).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Software '{name}' not registered — add it via /settings/software first")
    if not row.server_enabled:
        raise HTTPException(status_code=503, detail=f"Software '{name}' is disabled server-side")

    row.health          = body.health
    row.last_heartbeat  = datetime.now(timezone.utc)
    if body.details is not None:
        row.details = body.details

    db.commit()
    db.refresh(row)
    return _format(row)
