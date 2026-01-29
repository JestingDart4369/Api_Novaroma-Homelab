# Claude.md

## Project Overview

This is a **FastAPI API Gateway** that proxies external APIs (OpenWeather, Geoapify) while handling authentication and user management server-side. Provider API keys are never exposed to clients.

## Tech Stack

- **Framework**: FastAPI (Python 3.12)
- **Database**: SQLite with SQLAlchemy ORM
- **Auth**: JWT Bearer tokens (python-jose + passlib/bcrypt)
- **HTTP Client**: httpx (async)
- **Deployment**: Docker + Docker Compose + Cloudflare Tunnel

## Project Structure

```
app/
├── main.py          # FastAPI app entry, bootstrap admin, /auth/login
├── db.py            # SQLAlchemy engine, sessionmaker, Base class
├── deps.py          # Dependency injection (get_db)
├── models.py        # User model
├── auth.py          # JWT creation/decoding, password hashing
├── security.py      # Bearer token extraction, get_current_user, require_admin
└── routes/
    ├── users.py     # Admin endpoints: create/list/enable/disable users
    ├── weather.py   # GET /weather?city= (OpenWeather proxy)
    └── geocode.py   # GET /geocode?text= (Geoapify proxy)
```

## Key Patterns

### Authentication Flow
1. User calls `POST /auth/login` with `{"username": "...", "password": "..."}`
2. Server returns `{"access_token": "...", "token_type": "bearer"}`
3. Client includes `Authorization: Bearer <token>` header on protected routes

### Adding New Proxy Endpoints
1. Create `app/routes/<provider>.py`
2. Store API key in environment variable
3. Use `httpx.AsyncClient` for external calls
4. Protect with `Depends(get_current_user)`
5. Register router in `app/main.py`

### User Roles
- `user`: Can access proxy endpoints
- `admin`: Can also manage users via `/users` endpoints

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Secret key for signing JWTs |
| `OPENWEATHER_KEY` | OpenWeather API key |
| `GEOAPIFY_KEY` | Geoapify API key |
| `BOOTSTRAP_ADMIN_USERNAME` | Initial admin username (first run only) |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial admin password (first run only) |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel token |

## Database

- SQLite file: `/app/data/gateway.db` (Docker volume mounted)
- Single table: `users` (id, username, password_hash, role, is_active)
- Tables auto-created on startup via `Base.metadata.create_all()`

## Running Locally

```bash
# With Docker
docker compose up -d --build

# Without Docker (for development)
pip install -r requirements.txt
# Create data directory and set DB_URL in db.py to local path
uvicorn app.main:app --reload --port 8080
```

## Testing Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Login
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"eric","password":"ChangeThisPasswordNow"}'

# Use token
curl "http://localhost:8080/weather?city=London" \
  -H "Authorization: Bearer <TOKEN>"
```

## Common Tasks

### Add a new user (as admin)
```bash
curl -X POST http://localhost:8080/users \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","password":"secret","role":"user"}'
```

### Disable a user
```bash
curl -X POST http://localhost:8080/users/2/disable \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

## Security Notes

- Passwords hashed with bcrypt
- JWT tokens expire after 1 hour
- API keys stored server-side only, never sent to clients
- Disabled users cannot authenticate even with valid tokens
