# ============================================================
# IMPORTS
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User
from app.auth import hash_password
from app.security import require_admin, require_super_admin, require_root

# ============================================================
# ROUTER SETUP
# ============================================================
router = APIRouter(prefix="/users")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET    /settings/users            - list all users        → admin, superAdmin, Root
# POST   /settings/users            - create user           → admin, superAdmin, Root
# GET    /settings/users/{user_id}  - get single user       → admin, superAdmin, Root
# PUT    /settings/users/{user_id}  - update role/password  → superAdmin, Root
# POST   /settings/users/{user_id}/enable   - enable user   → admin, superAdmin, Root
# POST   /settings/users/{user_id}/disable  - disable user  → admin, superAdmin, Root
# DELETE /settings/users/{user_id}  - delete user           → Root only
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"  # default role for new users

class UserUpdate(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

# ============================================================
# ENDPOINTS
# ============================================================

# --- List all users (admin+) ---
@router.get("")
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = db.query(User).all()
    return [UserResponse(id=u.id, username=u.username, role=u.role, is_active=u.is_active) for u in users]


# --- Get single user (admin+) ---
@router.get("/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


# --- Create user (admin+) ---
@router.post("")
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not body.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    if body.role not in ("user", "admin", "superAdmin", "Root"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be: user, admin, superAdmin, Root")

    if db.query(User).filter(User.username == body.username.strip()).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


# --- Update user role / password (superAdmin+) ---
@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent modifying your own role
    if user_id == super_admin.id and body.role is not None:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    if body.role is not None:
        if body.role not in ("user", "admin", "superAdmin", "Root"):
            raise HTTPException(status_code=400, detail="Invalid role. Must be: user, admin, superAdmin, Root")
        user.role = body.role

    if body.password is not None:
        user.password_hash = hash_password(body.password)

    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


# --- Enable user (admin+) ---
@router.post("/{user_id}/enable")
def enable_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()
    return {"id": user.id, "username": user.username, "is_active": True}


# --- Disable user (admin+) ---
@router.post("/{user_id}/disable")
def disable_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent disabling yourself
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = False
    db.commit()
    return {"id": user.id, "username": user.username, "is_active": False}


# --- Delete user (Root only) ---
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    root: User = Depends(require_root),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting yourself
    if user_id == root.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    db.delete(user)
    db.commit()
    return {"detail": f"User '{user.username}' deleted"}
