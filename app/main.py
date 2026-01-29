import os
from fastapi import FastAPI, Depends, HTTPException
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from app.db import Base, engine
from app.deps import get_db
from app.models import User
from app.auth import verify_login, create_token, hash_password
from app.routes.weather import router as weather_router
from app.routes.geocode import router as geocode_router
from app.routes.users import router as users_router

app = FastAPI(title="API Gateway")

# Create tables
Base.metadata.create_all(bind=engine)

def bootstrap_admin_if_needed():
    """
    If no users exist, create an admin user from BOOTSTRAP_ADMIN_* env vars.
    Safe for first-run in Docker.
    """
    username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not username or not password:
        return

    db = next(get_db())  # quick bootstrap session
    try:
        if db.query(User).count() == 0:
            admin = User(
                username=username.strip(),
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

bootstrap_admin_if_needed()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/login", tags=["auth"])
def login(body: dict, db: Session = Depends(get_db)):
    username = body.get("username", "")
    password = body.get("password", "")
    user = verify_login(db, username, password)
    return {"access_token": create_token(user), "token_type": "bearer"}

app.include_router(weather_router)
app.include_router(geocode_router)
app.include_router(users_router)
