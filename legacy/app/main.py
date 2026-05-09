import os
import sys
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from app.db import Base, engine
from app.deps import get_db
from app.models import User, ApiConfig, RoleLimits
from app.config import load_all_api_configs, load_all_role_configs
from app.auth import hash_password, verify_login, create_token
from app.notifications import notify_startup_error, notify_startup_success
from app.routes.settings import router as settings_router
from app.routes.weather import router as weather_router
from app.routes.geo import router as geo_router
from app.routes.telephone import router as telephone_router
from app.routes.nasa import router as nasa_router
from app.routes.library import router as library_router
from app.routes.email import router as email_router
from app.routes.software import router as software_router
from app.routes.hardware import router as hardware_router
from app.routes.rate_limits import router as rate_limits_router
from app.routes.pushcut import router as pushcut_router
from app.rate_limit import add_rate_limit_headers
from app.routes.Grade import router as grade_router

app = FastAPI(
    title="API Gateway",
    description="Centralized API proxy with rate limiting for weather, geocoding, location, telephone directory, NASA space data, Open Library book services, and iOS automation (Pushcut) | © 2026 JestingDart4369",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


def initialize_server():
    """
    Initialize server: create tables, bootstrap admin, send startup notification.
    Sends email alert if initialization fails.
    """
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)

        db = next(get_db())
        try:
            # Bootstrap Root user if needed
            username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME")
            password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")

            if username and password:
                if db.query(User).count() == 0:
                    admin = User(
                        username=username.strip(),
                        password_hash=hash_password(password),
                        role="Root",
                        is_active=True,
                    )
                    db.add(admin)
                    db.commit()
                    print(f"[BOOTSTRAP] Created Root user: {username}")

            # Seed role_limits if empty (reads from .env via config.py)
            if db.query(RoleLimits).count() == 0:
                for role in load_all_role_configs():
                    db.add(RoleLimits(role_name=role["role_name"], max_calls_per_hour=role["max_calls_per_hour"], is_active=True))
                db.commit()
                print("[BOOTSTRAP] Seeded role_limits table")

            # Seed api_config if empty (reads from .env via config.py)
            if db.query(ApiConfig).count() == 0:
                for api in load_all_api_configs():
                    db.add(ApiConfig(api_name=api["name"], max_calls_per_hour=api["max_calls_per_hour"], is_active=api["enabled"]))
                db.commit()
                print("[BOOTSTRAP] Seeded api_config table")

        finally:
            db.close()

        # Send success notification
        notify_startup_success()
        print("[SERVER] API Gateway started successfully")

    except Exception as e:
        print(f"[CRITICAL] Server initialization failed: {e}")
        notify_startup_error(e)
        sys.exit(1)

# Initialize server on startup
initialize_server()

#The main Page
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Serve the homepage of the api"""
    template_path = Path(__file__).parent / "templates" / "index.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

#check if the Server is up
@app.get("/health")
def health():
    """Show if service is up"""
    return {"ok": True}

#Login for accounts
@app.post("/auth/login", tags=["auth"])
def login(body: dict, db: Session = Depends(get_db)):
    username = body.get("username", "")
    password = body.get("password", "")
    user = verify_login(db, username, password)
    return {"access_token": create_token(user), "token_type": "bearer"}

# ============================================================
# MIDDLEWARE
# ============================================================
app.middleware("http")(add_rate_limit_headers)

# ============================================================
# ROUTERS
# ============================================================
app.include_router(settings_router)
app.include_router(weather_router)
app.include_router(geo_router)
app.include_router(telephone_router)
app.include_router(nasa_router)
app.include_router(library_router)
app.include_router(email_router)
app.include_router(pushcut_router)
app.include_router(software_router)
app.include_router(hardware_router)
app.include_router(rate_limits_router)
app.include_router(grade_router)