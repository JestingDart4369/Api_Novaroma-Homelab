from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.deps import get_db
from app.models import User
from app.auth import hash_password
from app.security import require_admin

router = APIRouter(prefix="/users", tags=["users"])

@router.post("")
def create_user(body: dict, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    role = body.get("role", "user")

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'admin'")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="username already exists")

    u = User(username=username, password_hash=hash_password(password), role=role, is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active}

@router.get("")
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active} for u in users]

@router.post("/{user_id}/disable")
def disable_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    u.is_active = False
    db.commit()
    return {"id": u.id, "disabled": True}

@router.post("/{user_id}/enable")
def enable_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    u.is_active = True
    db.commit()
    return {"id": u.id, "enabled": True}
