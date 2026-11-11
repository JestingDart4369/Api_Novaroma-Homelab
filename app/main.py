import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import FileResponse
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

app = FastAPI(
    title="Novaroma API Gateway",
    description="API Gateway for Novaroma Homelab — proxies external APIs with JWT authentication.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(static_dir / "index.html")

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — Docs",
        swagger_css_url="/static/swagger-novaroma.css",
        swagger_favicon_url="",
    )

@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — ReDoc",
        redoc_favicon_url="",
    )

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
