import os
import sys
import httpx
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from app.db import Base, engine
from app.deps import get_db
from app.models import User, ApiConfig, RoleLimits
from app.config import load_all_api_configs, load_all_role_configs
from app.auth import hash_password, verify_login, create_token, check_login_budget, get_pepper, validate_jwt_secret
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
from app.cors import allowed_origins
from app.routes.Grade import router as grade_router

app = FastAPI(
    title="API Gateway",
    description="Centralized API proxy with rate limiting for weather, geocoding, location, telephone directory, NASA space data, Open Library book services, and iOS automation (Pushcut) | © 2026 JestingDart4369",
    version="1.0.0",
    docs_url=None,
    redoc_url=None
)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default "input" and context may contain passwords/tokens.
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': error['loc'], 'type': error['type'], 'msg': 'Invalid request value'}
        for error in exc.errors()
    ]})


@app.exception_handler(httpx.RequestError)
async def upstream_transport_error(request, exc):
    # Handled exceptions avoid logging URLs with provider keys in tracebacks.
    return JSONResponse(status_code=502, content={'detail': 'Upstream service unavailable'})


def initialize_server():
    """
    Initialize server: create tables, bootstrap admin, send startup notification.
    Sends email alert if initialization fails.
    """
    try:
        validate_jwt_secret()
        get_pepper()
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
        print(f"[CRITICAL] Server initialization failed: {type(e).__name__}")
        notify_startup_error(e)
        sys.exit(1)

# Initialize server on startup
initialize_server()

FONT_LINK = '<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;600;700&display=swap" rel="stylesheet">'
ICON_LINK = '<link rel="icon" type="image/webp" href="/logo.webp">'

# Logo from the Nova Roma design system (header, favicon, ReDoc sidebar)
@app.get("/logo.webp", include_in_schema=False)
async def logo():
    return FileResponse(
        Path(__file__).parent / "static" / "nova-roma-logo-256.webp",
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"},
    )

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schema["info"]["x-logo"] = {"url": "/logo.webp", "altText": "Novaroma Logo", "backgroundColor": "#eee3c9"}
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi

SEASON_JS = """
function novaromaSeason() {
    var m = new Date().getMonth() + 1;
    if (m >= 3 && m <= 5) return ['spring', 'Frühling'];
    if (m >= 6 && m <= 8) return ['summer', 'Sommer'];
    if (m >= 9 && m <= 11) return ['autumn', 'Herbst'];
    return ['winter', 'Winter'];
}
"""

SWAGGER_HEADER = (
    '<header class="nr-header">'
    '<img src="/logo.webp" alt="Novaroma Logo" width="48" height="48">'
    '<div><div class="nr-title">Novaroma-Homelab</div><div class="nr-sub">API Docs</div></div>'
    '<span class="nr-season" id="nr-season"></span></header>'
    '<script>' + SEASON_JS +
    'var s = novaromaSeason(); document.documentElement.dataset.season = s[0];'
    'document.getElementById("nr-season").textContent = s[1];</script>'
)

# Swagger UI / ReDoc with the Nova Roma design system
@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def swagger_docs():
    css = (Path(__file__).parent / "templates" / "swagger-novaroma.css").read_text(encoding="utf-8")
    page = get_swagger_ui_html(openapi_url=app.openapi_url, title="Novaroma API Gateway - Docs").body.decode()
    page = page.replace("</head>", f"{ICON_LINK}{FONT_LINK}<style>{css}</style></head>", 1)
    return page.replace("<body>", f"<body>{SWAGGER_HEADER}", 1)

REDOC_JS = "<script>" + SEASON_JS + """
(function () {
    var s = novaromaSeason()[0];
    var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var light = {
        spring: ['#fbf3f6', '#8e6271'], summer: ['#fdf8ea', '#836e42'],
        autumn: ['#f8f0e6', '#85664c'], winter: ['#f1f5fa', '#5c7084']
    };
    var night = {
        spring: ['#1f0f14', '#cfa6b6'], summer: ['#1d1608', '#cdb67e'],
        autumn: ['#1d1109', '#cfa883'], winter: ['#0e1620', '#9db6cc']
    };
    var p = (dark ? night : light)[s];
    var main = dark ? '#eee3c9' : '#5e282c';
    var text = dark ? '#fff8ea' : '#190607';
    var accent = dark ? '#6e3338' : '#eee3c9';
    var font = 'Roboto, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    var theme = {
        typography: { fontFamily: font, headings: { fontFamily: font }, code: { fontFamily: 'monospace' } },
        colors: { primary: { main: main }, text: { primary: text, secondary: p[1] } },
        sidebar: { backgroundColor: accent, textColor: text },
        rightPanel: { backgroundColor: dark ? '#120808' : '#5e282c', textColor: '#eee3c9' }
    };
    document.querySelector('redoc').setAttribute('theme', JSON.stringify(theme));
    var css = document.createElement('style');
    css.textContent = 'body{background:' + p[0] + ';margin:0}.api-content{background:' + p[0] + '}';
    document.head.appendChild(css);
})();
</script>"""

@app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
async def redoc_docs():
    page = get_redoc_html(openapi_url=app.openapi_url, title="Novaroma API Gateway - ReDoc").body.decode()
    page = page.replace("</head>", f"{ICON_LINK}{FONT_LINK}</head>", 1)
    return page.replace("</redoc>", f"</redoc>{REDOC_JS}", 1)

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
def login(body: dict, request: Request, db: Session = Depends(get_db)):
    username = body.get("username", "")
    password = body.get("password", "")
    if (not isinstance(username, str) or not isinstance(password, str)
            or len(username) > 50 or len(password.encode('utf-8')) > 16384):
        raise HTTPException(400, 'Invalid login data')
    check_login_budget(db.get_bind(), username, request)
    user = verify_login(db, username, password)
    return {"access_token": create_token(user), "token_type": "bearer"}

# ============================================================
# MIDDLEWARE
# ============================================================
app.middleware("http")(add_rate_limit_headers)

# Added last so it is the outermost layer and answers preflight requests before anything else.
# Auth is a Bearer header (no cookies), so credentials stay disabled.
_cors_origins = allowed_origins()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        max_age=600,
    )

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