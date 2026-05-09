from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.deps import get_db
from app.auth import decode_token
from app.models import User

bearer = HTTPBearer()

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(creds.credentials)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "superAdmin", "Root"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user

def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("superAdmin", "Root"):
        raise HTTPException(status_code=403, detail="Super Admin only")
    return user

def require_root(user: User = Depends(get_current_user)) -> User:
    if user.role !="Root":
        raise HTTPException(status_code=403, detail="Root only")
    return user