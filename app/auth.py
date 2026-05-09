import os
import time
import hashlib
from jose import jwt, JWTError
from passlib.hash import bcrypt
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import User

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"

#Text to the Hashed (Password)
def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; pre-hash long passwords with SHA-256
    if len(password.encode('utf-8')) > 72:
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return bcrypt.hash(password)

#See if password Match
def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.verify(password, password_hash)

#Create the bearer token payload
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

#decode the token to see if its right
def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

#see if the user exist
def verify_login(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Bad credentials")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Bad credentials")
    return user