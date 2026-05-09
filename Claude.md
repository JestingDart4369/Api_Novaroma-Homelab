# CLAUDE.md

## Project Overview

This is a **FastAPI API Gateway** that proxies external APIs (OpenWeather, Geoapify, IPRegistry, Resend, search.ch, NASA, Open Library, Pushcut) while handling authentication and user management server-side. Provider API keys are never exposed to clients. It also provides a **push-based health monitoring system** for custom software and hardware: registered services and devices call in their own status via heartbeat endpoints, and clients read the aggregated health dashboard.

All API and role configuration flows from `.env` → `config.py` → DB seeding → runtime checks. The DB is the single source of truth after the initial seed; values can be adjusted live via the `/settings` admin endpoints without restarting the server.

**Public URL**: https://api.novaroma-homelab.uk

## Tech Stack

- **Framework**: FastAPI (Python 3.12)
- **Database**: SQLite with SQLAlchemy ORM (5 tables)
- **Auth**: JWT Bearer tokens (python-jose + passlib/bcrypt)
- **HTTP Client**: httpx (async)
- **Deployment**: Docker + Docker Compose + Cloudflare Tunnel

## Project Structure

```
app/
├── main.py          # FastAPI app entry, bootstrap Root user, seed DB, /auth/login, middleware + router registration
├── db.py            # SQLAlchemy engine (DB_URL env var or ./data/gateway.db), sessionmaker, Base class
├── deps.py          # Dependency injection (get_db)
├── models.py        # ORM models: User, ApiConfig, RoleLimits, Software, Hardware
├── config.py        # API_REGISTRY, ROLE_ENV_VARS, ROLE_DEFAULTS, loader functions (get_key, load_all_*)
├── auth.py          # JWT creation/decoding, password hashing (SHA-256 pre-hash + bcrypt)
├── security.py      # Bearer token extraction, get_current_user, require_admin, require_super_admin, require_root
├── notifications.py # Email alerts for server errors and critical events
├── rate_limit.py    # Per-user and per-API rate limiting (in-memory store, DB-backed limits)
├── templates/
│   └── index.html   # Documentation homepage with seasonal themes
└── routes/
    ├── weather.py      # GET /weather, /weather/forecast/hourly, /weather/forecast/daily
    ├── geo.py          # GET /geo/geocode (Geoapify), /geo/ip (IPRegistry)
    ├── telephone.py    # GET /telephone/search (search.ch)
    ├── nasa.py         # GET /nasa/apod, /nasa/epic/{collection}, /nasa/epic/{collection}/available
    ├── library.py      # GET /library/search, /library/books, /library/covers/*, /library/works/*,
    │                   #     /library/authors/*, /library/subjects/*, /library/archive/* (S3)
    ├── email.py        # POST /email/send, /email/send-simple
    ├── pushcut.py      # GET /pushcut/devices, /pushcut/notifications, /pushcut/subscriptions,
    │                   #     POST /pushcut/notifications/{name}, /pushcut/execute, /pushcut/subscriptions,
    │                   #     DELETE /pushcut/subscriptions/{id}
    ├── Grade.py        # POST /grade/user/auth, /grade/user, GET /grade/user, PATCH /grade/user,
    │                   #     DELETE /grade/user, GET/POST/PUT/DELETE /grade/subjects,
    │                   #     GET /grade/subjects/exams, GET /grade/exam,
    │                   #     POST/PUT/DELETE /grade/exams (proxy: api.sercraft.ch)
    ├── software.py     # GET /software, /software/{name}, POST /software/{name}/heartbeat
    ├── hardware.py     # GET /hardware, /hardware/{name}, POST /hardware/{name}/heartbeat
    ├── rate_limits.py  # GET /rate-limits/me, /rate-limits/apis, /rate-limits/all
    └── settings/
        ├── __init__.py # Assembles sub-routers under /settings prefix
        ├── users.py    # CRUD for users (/settings/users)
        ├── apis.py     # API config management (/settings/apis)
        ├── roles.py    # Role limit management (/settings/roles)
        ├── software.py # Register / enable / delete software (/settings/software)
        └── hardware.py # Register / update config / delete hardware (/settings/hardware)
```

## Documentation Structure

### Public Documentation (in Git)
- **README.md** - Main project documentation with quick start
- **CONTRIBUTING.md** - Contribution guidelines and development setup
- **SECURITY.md** - Security policy and vulnerability reporting
- **RATE_LIMITING.md** - Comprehensive rate limiting guide
- **RATE_LIMITING_QUICKSTART.md** - Quick start guide for rate limiting
- **RATE_LIMITING_SUMMARY.md** - Implementation summary
- **CHANGELOG_RATE_LIMITING.md** - Rate limiting changelog
- **LICENSE** - MIT License
- **CLAUDE.md** - This file (AI context and developer notes)
- **.github/** - Issue templates and PR template

### Internal Documentation (local only, gitignored)
- **internal-docs/wiki-pages/** - Wiki content ready for GitHub wiki upload
- **internal-docs/docs/** - Additional documentation and guides
- **internal-docs/FINAL_CHECKLIST.md** - Deployment checklist
- **internal-docs/MIGRATION_SUMMARY.md** - Migration notes
- **internal-docs/upload-wiki.ps1** - Automated wiki upload script

## Key Patterns

### Authentication Flow
1. User calls `POST /auth/login` with `{"username": "...", "password": "..."}`
2. Server returns `{"access_token": "...", "token_type": "bearer"}`
3. Client includes `Authorization: Bearer <token>` header on protected routes

### User Roles (4 levels, lowest → highest)
| Role | What it can do |
|------|----------------|
| `user` | Call all proxy API endpoints |
| `admin` | All of the above + list/create/enable/disable users, view all settings |
| `superAdmin` | All of the above + change user roles/passwords, toggle APIs on/off, adjust API call limits |
| `Root` | All of the above + delete users, change role rate limits. Only one created automatically at bootstrap |

The bootstrap user (created on first run from `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`) is assigned the `Root` role.

### Server Notifications
The server automatically sends email alerts to `ADMIN_EMAIL` for:
- **Startup Success**: Server started and ready
- **Startup Failure**: Server failed to initialize (with error details)
- **Critical Errors**: Runtime errors that need immediate attention

All server notifications come from `SERVER_FROM_EMAIL` (apiserver@api.novaroma-homelab.uk).

### Rate Limiting
The rate limiting system has two layers:

**Per-User Limits** (role-based, from `role_limits` table):
- `user`: 1000 req/hour
- `admin`: 2000 req/hour
- `superAdmin`: 5000 req/hour
- `Root`: 10000 req/hour
- Tracked in-memory per user in hourly buckets

**Per-API Limits** (from `api_config` table):
- Each external API has its own quota (e.g. NASA: 900/hour, OpenWeather: 3000/hour)
- If an API is disabled (`is_active = false`) → 503
- If an API's quota is exceeded → 429

Both layers are checked on every request. Limits are seeded from `.env` on first run, then live-editable via `/settings/apis` and `/settings/roles`.

- **Automatic Cleanup**: Expired hour buckets removed every 5 minutes
- **Response Headers**: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
- **HTTP 429**: Proper error responses with Retry-After header

See `RATE_LIMITING.md` for comprehensive documentation.

### Adding New Proxy Endpoints

**See `docs/ADD_NEW_API_TEMPLATE.md` for a comprehensive step-by-step guide with examples.**

Quick steps:
1. Add to `.env`:
   ```
   MYAPI_KEY=your_key_here
   MYAPI_ENABLED=true
   MYAPI_MAX_CALLS=1000
   ```
2. Add one line to `API_REGISTRY` in `app/config.py`:
   ```python
   "myapi": "MYAPI",
   ```
3. Create `app/routes/myapi.py` following the blueprint pattern (IMPORTS / ROUTER SETUP / ROUTE SCHEMA / ENDPOINTS)
4. Use `httpx.AsyncClient` for external calls, `get_key("myapi")` to read the key
5. Protect with `Depends(get_current_user)` + `Depends(check_user_rate_limit)` + `Depends(APIRateLimiter("myapi"))`
6. Register the router in `app/main.py`

The DB will auto-seed the new API's config on next restart (if `api_config` table is empty). If the table already has rows, add the new API manually via `/settings/apis` or delete `data/gateway.db` to re-seed.

## Environment Variables

**CRITICAL: Never commit `.env` file to Git!** It's in `.gitignore` and contains all API keys and secrets.

### Core / Auth
| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Secret key for signing JWTs |
| `BOOTSTRAP_ADMIN_USERNAME` | Initial Root user username (first run only) |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial Root user password (first run only) |

### API Keys & Settings (per-API pattern: `{PREFIX}_KEY`, `{PREFIX}_ENABLED`, `{PREFIX}_MAX_CALLS`)
| Prefix | Service | Key var | Enabled var | Max calls var |
|--------|---------|---------|-------------|---------------|
| `OPENWEATHER` | Weather + forecasts | `OPENWEATHER_KEY` | `OPENWEATHER_ENABLED` | `OPENWEATHER_MAX_CALLS` |
| `GEOAPIFY` | Geocoding | `GEOAPIFY_KEY` | `GEOAPIFY_ENABLED` | `GEOAPIFY_MAX_CALLS` |
| `IPREGISTRY` | IP geolocation | `IPREGISTRY_KEY` | `IPREGISTRY_ENABLED` | `IPREGISTRY_MAX_CALLS` |
| `RESEND` | Email | `RESEND_KEY` | `RESEND_ENABLED` | `RESEND_MAX_CALLS` |
| `TELEPHONE` | Swiss telephone directory | `TELEPHONE_KEY` | `TELEPHONE_ENABLED` | `TELEPHONE_MAX_CALLS` |
| `NASA` | APOD + EPIC | `NASA_KEY` | `NASA_ENABLED` | `NASA_MAX_CALLS` |
| `OPENLIBRARY` | Books + S3 archive | `OPENLIBRARY_KEY` | `OPENLIBRARY_ENABLED` | `OPENLIBRARY_MAX_CALLS` |
| `PUSHCUT` | iOS automation + notifications | `PUSHCUT_KEY` | `PUSHCUT_ENABLED` | `PUSHCUT_MAX_CALLS` |

`OPENLIBRARY` also needs `OPENLIBRARY_SECRET` for Internet Archive S3 access.

### Role Rate Limits
| Variable | Default | Purpose |
|----------|---------|---------|
| `ROLE_USER_MAX_CALLS` | 1000 | Max requests/hour for `user` role |
| `ROLE_ADMIN_MAX_CALLS` | 2000 | Max requests/hour for `admin` role |
| `ROLE_SUPERADMIN_MAX_CALLS` | 5000 | Max requests/hour for `superAdmin` role |
| `ROLE_ROOT_MAX_CALLS` | 10000 | Max requests/hour for `Root` role |

### Email
| Variable | Purpose |
|----------|---------|
| `DEFAULT_FROM_EMAIL` | Default sender for client email requests |
| `SERVER_FROM_EMAIL` | Sender for server alerts |
| `ADMIN_EMAIL` | Email address to receive server alerts |
| `EMAIL_DOMAIN` | Domain for RECIPIENTS in `/email/send-simple` (e.g., `novaroma-homelab.uk`) |
| `SENDER_DOMAIN` | Domain for SENDERS - must be verified in Resend (e.g., `api.novaroma-homelab.uk`) |

### Deployment
| Variable | Purpose |
|----------|---------|
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel token |
| `DB_URL` | SQLAlchemy database URL (optional; defaults to `./data/gateway.db`) |

## Database

- **Engine**: SQLite via SQLAlchemy ORM
- **File**: `data/gateway.db` (local dev) or `/app/data/gateway.db` (Docker). Override with `DB_URL` env var.
- **Tables** (auto-created on startup via `Base.metadata.create_all()`):

| Table | Columns | Purpose |
|-------|---------|---------|
| `users` | id, username, password_hash, role, is_active | User accounts and credentials |
| `api_config` | id, api_name, is_active, max_calls_per_hour | Per-API rate limits and on/off toggle |
| `role_limits` | id, role_name, max_calls_per_hour, is_active | Per-role hourly request limits |
| `software` | id, name, health, last_heartbeat, details (JSON), is_active | Registered software health entries |
| `hardware` | id, name, health, last_heartbeat, config (JSON), details (JSON), is_active | Registered hardware entries with config |

`users`, `api_config`, and `role_limits` are seeded from `.env` on first run (when empty). `software` and `hardware` are populated manually via `/settings/software` and `/settings/hardware`. All tables are live-editable via `/settings` endpoints without restarting the server.

## Running Locally

```bash
# With Docker
docker compose up -d --build

# Without Docker (for development)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Make sure `data/` directory exists at the project root for the local SQLite file.

## Testing Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Login
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your-username","password":"your-password"}'

# --- Weather ---
curl "http://localhost:8080/weather?city=London" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/weather/forecast/hourly?lat=51.5074&lon=-0.1278" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/weather/forecast/daily?lat=51.5074&lon=-0.1278&cnt=7" \
  -H "Authorization: Bearer <TOKEN>"

# --- Location ---
curl "http://localhost:8080/geo/geocode?text=London" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/geo/ip" \
  -H "Authorization: Bearer <TOKEN>"

# --- Telephone ---
curl "http://localhost:8080/telephone/search?was=Meier&wo=Zurich" \
  -H "Authorization: Bearer <TOKEN>"

# --- NASA ---
curl "http://localhost:8080/nasa/apod" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/nasa/apod?date=2024-12-25&hd=true" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/nasa/epic/natural" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/nasa/epic/natural/available" \
  -H "Authorization: Bearer <TOKEN>"

# --- Library ---
curl "http://localhost:8080/library/search?q=lord+of+the+rings&limit=5" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/library/books?bibkeys=ISBN:0451526538" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/library/covers/b/isbn:0451526538?size=M" \
  -H "Authorization: Bearer <TOKEN>" > cover.jpg

curl "http://localhost:8080/library/authors/OL26320A" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/library/subjects/science_fiction?limit=20" \
  -H "Authorization: Bearer <TOKEN>"

# --- Email ---
curl -X POST "http://localhost:8080/email/send" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"to":["recipient@example.com"],"subject":"Test","html":"<p>Hello!</p>","from_email":"YourApp <app@your-domain.com>"}'

curl -X POST "http://localhost:8080/email/send-simple" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"to_users":["recipient"],"subject":"Test","html":"<p>Hello!</p>","from_name":"YourApp"}'
# to_users uses EMAIL_DOMAIN, from_name uses verified sender from SENDER_DOMAIN

# --- Pushcut (iOS Automation) ---
# List devices
curl "http://localhost:8080/pushcut/devices" \
  -H "Authorization: Bearer <TOKEN>"

# List notifications
curl "http://localhost:8080/pushcut/notifications" \
  -H "Authorization: Bearer <TOKEN>"

# Send notification
curl -X POST "http://localhost:8080/pushcut/notifications/MyNotification?text=Hello&title=Test" \
  -H "Authorization: Bearer <TOKEN>"

# Execute iOS shortcut
curl -X POST "http://localhost:8080/pushcut/execute?shortcut=MyShortcut&input=test" \
  -H "Authorization: Bearer <TOKEN>"

# Execute HomeKit scene
curl -X POST "http://localhost:8080/pushcut/execute" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"homekit":"Good Morning","delay":5}'

# List webhook subscriptions
curl "http://localhost:8080/pushcut/subscriptions" \
  -H "Authorization: Bearer <TOKEN>"

# --- Rate Limits ---
curl "http://localhost:8080/rate-limits/me" \
  -H "Authorization: Bearer <TOKEN>"

curl "http://localhost:8080/rate-limits/apis" \
  -H "Authorization: Bearer <TOKEN>"

# --- Software Health ---
# List all software
curl "http://localhost:8080/software" \
  -H "Authorization: Bearer <TOKEN>"

# Get one software's health (stale: true if no heartbeat in 5 min)
curl "http://localhost:8080/software/my-app" \
  -H "Authorization: Bearer <TOKEN>"

# Software pushes its own heartbeat
curl -X POST "http://localhost:8080/software/my-app/heartbeat" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"health":"ok","details":{"version":"2.1","uptime_seconds":3600}}'

# --- Hardware Health ---
# List all hardware
curl "http://localhost:8080/hardware" \
  -H "Authorization: Bearer <TOKEN>"

# Get one device (health + config)
curl "http://localhost:8080/hardware/router-hall" \
  -H "Authorization: Bearer <TOKEN>"

# Device pushes heartbeat with config
curl -X POST "http://localhost:8080/hardware/router-hall/heartbeat" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"health":"ok","config":{"ip":"192.168.1.1","firmware":"v3.2"},"details":{"cpu_temp_c":42}}'

# --- Settings (admin+) ---
curl "http://localhost:8080/settings/users" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

curl "http://localhost:8080/settings/apis" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

curl "http://localhost:8080/settings/roles" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

curl "http://localhost:8080/settings/software" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

curl "http://localhost:8080/settings/hardware" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

## Common Tasks

### Add a new user (admin+)
```bash
curl -X POST http://localhost:8080/settings/users \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","password":"secret","role":"user"}'
```

### Disable a user (admin+)
```bash
curl -X POST http://localhost:8080/settings/users/2/disable \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Toggle an API on/off (superAdmin+)
```bash
curl -X PUT http://localhost:8080/settings/apis/nasa \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

### Change a role's rate limit (Root only)
```bash
curl -X PUT http://localhost:8080/settings/roles/user \
  -H "Authorization: Bearer <ROOT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"max_calls_per_hour": 2000}'
```

### Register a new software entry (admin+)
```bash
curl -X POST http://localhost:8080/settings/software \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-app"}'
```

### Register a new hardware device (admin+, optional initial config)
```bash
curl -X POST http://localhost:8080/settings/hardware \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name":"router-hall","config":{"ip":"192.168.1.1","location":"hallway"}}'
```

### Update hardware config (superAdmin+)
```bash
curl -X PUT http://localhost:8080/settings/hardware/router-hall \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"config":{"ip":"192.168.1.2","location":"hallway","firmware":"v3.3"}}'
```

### Kill-Switch: Remotely disable software/hardware (superAdmin+)
```bash
# Disable software (next heartbeat gets 503 → client exits)
curl -X PUT http://localhost:8080/settings/software/my-app \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Disable hardware
curl -X PUT http://localhost:8080/settings/hardware/router-hall \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Re-enable
curl -X PUT http://localhost:8080/settings/software/my-app \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

**How it works:**
1. SuperAdmin sets `is_active=false` via PUT `/settings/software/{name}` or `/settings/hardware/{name}`
2. Next heartbeat from that service/device receives **503** response
3. Client heartbeat handler automatically exits the process

**Permissions:**
- `admin` → can register new software/hardware
- `superAdmin` → can kill (toggle is_active)
- `Root` → can kill + delete entries

## Security Notes

### API Key Protection
- **ALL external API keys stored server-side only** in `.env` file
- `.env` is in `.gitignore` and NEVER committed to Git
- Clients authenticate with username/password to get JWT token
- Clients never see or handle external API keys

### Authentication & Security
- Passwords hashed with bcrypt (SHA-256 pre-hash for passwords >72 bytes)
- JWT tokens expire after 1 hour
- Disabled users cannot authenticate even with valid tokens
- 4-level role-based access control: `user` → `admin` → `superAdmin` → `Root`
- **Rate limiting**: Per-user (role-based) and per-API limits to prevent abuse
- **Input validation**: Comprehensive validation on all endpoints
- **Audit logging**: All user actions logged for security monitoring
- **Root-only actions**: User deletion and role limit changes require Root role
- **Self-modification guards**: Admins cannot disable/delete their own account

### Protected Files
- `.env` - Contains ALL API keys, secrets, and email configuration (gitignored)
- `data/gateway.db` - SQLite database with user credentials (gitignored)
- `internal-docs/` - Internal documentation and dev notes (gitignored)
- Rate limit counters stored in-memory only (not persisted to disk)

### Email Configuration
**Client Emails** (sent via `/email/send` or `/email/send-simple`):
- `/email/send`: Full control over sender and recipient addresses
- `/email/send-simple`: Recipients use `EMAIL_DOMAIN`, senders use `SENDER_DOMAIN`
  - `to_users: ["user"]` → `user@EMAIL_DOMAIN` (e.g., `user@novaroma-homelab.uk`)
  - `from_name: "App"` → `App <Cmd@SENDER_DOMAIN>` (e.g., `App <Cmd@api.novaroma-homelab.uk>`)
  - `SENDER_DOMAIN` must be verified in Resend for emails to send successfully
- Use `DEFAULT_FROM_EMAIL` from `.env` if no from_email/from_name specified

**Server Emails** (automated alerts):
- Always use `SERVER_FROM_EMAIL` for server-generated alerts
- Sent to `ADMIN_EMAIL` for critical events
- No user authentication required (internal system)

## Documentation Homepage

The homepage (`app/templates/index.html`) features:
- **Seasonal Themes**: Automatically changes colors based on current month
  - Spring (Mar-May): Fresh greens
  - Summer (Jun-Aug): Bright blues
  - Autumn (Sep-Nov): Warm oranges
  - Winter (Dec-Feb): Cool blues
- **Interactive API Documentation**: Links to Swagger UI and ReDoc
- **GitHub Links**: Repository, wiki, and issues
- **Mobile Responsive**: Optimized for all screen sizes

## Deployment

### Docker Compose
```bash
# Start services
docker compose up -d --build

# View logs
docker compose logs -f api-gateway
docker compose logs -f cloudflared

# Restart
docker compose restart

# Stop
docker compose down
```

### Cloudflare Tunnel
- Configured via `CLOUDFLARE_TUNNEL_TOKEN`
- Public hostname: api.novaroma-homelab.uk
- Service: http://api-gateway:8080
- Automatic SSL/HTTPS

## GitHub Repository

- **Main Branch**: master
- **Public URL**: https://github.com/JestingDart4369/ApiServer_Novaroma
- **Wiki**: https://github.com/JestingDart4369/ApiServer_Novaroma/wiki
- **Issues**: https://github.com/JestingDart4369/ApiServer_Novaroma/issues

### Contributing
See CONTRIBUTING.md for development setup and guidelines.

### Security
See SECURITY.md for security policy and vulnerability reporting.

## Wiki Upload

Wiki pages are in `internal-docs/wiki-pages/` (gitignored, local only).

To upload to GitHub wiki:
1. Go to https://github.com/JestingDart4369/ApiServer_Novaroma/wiki
2. Create new page with filename (without .md)
3. Copy content from `internal-docs/wiki-pages/<filename>.md`
4. Paste and save

Available pages:
- Home.md
- Quick-Start-Guide.md
- Cloudflare-Tunnel-Setup.md
- Authentication.md
- Rate-Limiting.md (optional: copy from RATE_LIMITING.md)

## Production Status

- **Public URL**: https://api.novaroma-homelab.uk
- **Status**: Production ready with 4-role RBAC and comprehensive rate limiting
- **Docker**: Running
- **Cloudflare Tunnel**: Connected
- **Notifications**: Active (admin email alerts)
- **APIs**: 8 external services integrated (Weather, Geocoding, IP Location, Telephone, NASA, Books, Email, Pushcut iOS Automation)
- **Health Monitoring**: Push-based health for custom software and hardware (/software, /hardware + settings CRUD)
- **Rate Limiting**: Active (per-user role-based + per-API quotas, live-editable via /settings)
- **Security**: Input validation, audit logging, 4-level role hierarchy, self-modification guards

Built with love by JestingDart4369
