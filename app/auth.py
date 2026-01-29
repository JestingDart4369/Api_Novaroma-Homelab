import os
import time
from jose import jwt, JWTError
from passlib.hash import bcrypt
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import User

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.verify(password, password_hash)

def create_token(user: User) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user.id),          # stable identity
        "username": user.username,    # convenience
        "role": user.role,
        "iat": now,
        "exp": now + 3600,            # 1 hour
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def verify_login(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Bad credentials")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Bad credentials")
    return user
