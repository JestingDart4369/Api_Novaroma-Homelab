# Adding a New API Integration - Step-by-Step Template

This template provides a complete checklist for integrating a new external API into the FastAPI Gateway.

## Prerequisites

Before starting, gather the following information:

- [ ] **API Documentation URL**: _______________________
- [ ] **API Key / Credentials**: _______________________
- [ ] **Base URL**: _______________________
- [ ] **Authentication Method**: (API key header / Bearer token / Basic auth / etc.)
- [ ] **Rate Limits**: _______ requests per hour
- [ ] **Main Endpoints to Implement**: (list 3-5 most important endpoints)
  - [ ] Endpoint 1: _______________________
  - [ ] Endpoint 2: _______________________
  - [ ] Endpoint 3: _______________________

---

## Integration Steps

### Step 1: Add Environment Variables to `.env`

**File**: `D:\02_ApiServer\.env`

Add three variables following this pattern:

```env
# ============================================================
# API: [Service Name] ([brief description])
# ============================================================
[PREFIX]_KEY=your_api_key_here
[PREFIX]_ENABLED=true
[PREFIX]_MAX_CALLS=1000
```

**Example** (Pushcut):
```env
# ============================================================
# API: Pushcut (iOS automation & notifications)
# ============================================================
PUSHCUT_KEY=your_pushcut_api_key_here
PUSHCUT_ENABLED=true
PUSHCUT_MAX_CALLS=1000
```

**Tips**:
- Use UPPERCASE for the prefix (e.g., `PUSHCUT`, `NASA`, `OPENWEATHER`)
- Keep the prefix short but descriptive
- Set initial `MAX_CALLS` conservatively (adjust later based on your API plan)

**Checklist**:
- [ ] Added `[PREFIX]_KEY` variable
- [ ] Added `[PREFIX]_ENABLED` variable
- [ ] Added `[PREFIX]_MAX_CALLS` variable
- [ ] Verified `.env` is in `.gitignore` (never commit API keys!)

---

### Step 2: Register API in `API_REGISTRY`

**File**: `D:\02_ApiServer\app\config.py`

Add one line to the `API_REGISTRY` dictionary:

```python
API_REGISTRY = {
    "openweather": "OPENWEATHER",
    "geoapify":    "GEOAPIFY",
    "ipregistry":  "IPREGISTRY",
    "resend":      "RESEND",
    "telephone":   "TELEPHONE",
    "nasa":        "NASA",
    "openlibrary": "OPENLIBRARY",
    "pushcut":     "PUSHCUT",      # ← Add your API here
    "myapi":       "MYAPI",        # ← Your new API
}
```

**Notes**:
- **Key** (left side): lowercase, internal name used in routes and database
- **Value** (right side): UPPERCASE prefix from `.env` file
- Keep alphabetical order for readability

**Checklist**:
- [ ] Added API to `API_REGISTRY`
- [ ] Used lowercase for key (internal name)
- [ ] Used UPPERCASE for value (env prefix)
- [ ] Saved `app/config.py`

---

### Step 3: Create Route File

**File**: `D:\02_ApiServer\app\routes\[apiname].py`

Use this template structure:

```python
# ============================================================
# IMPORTS
# ============================================================
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional
from app.security import get_current_user
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/[apiname]", tags=["[apiname]"])
API_KEY = get_key("[apiname]")  # Internal name from API_REGISTRY
BASE_URL = "https://api.example.com/v1"  # API base URL

check_[apiname]_limit = APIRateLimiter("[apiname]")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET  /[apiname]/endpoint1  - Description
# POST /[apiname]/endpoint2  - Description
#
# Auth: Required (JWT Bearer token)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("[apiname]")
#
# Response:
#   200 - Success with JSON response
#   400 - Invalid parameters
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config
# ============================================================

# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/endpoint1")
async def get_endpoint1(
    param1: Optional[str] = Query(None, description="Parameter description"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_[apiname]_limit),
):
    """
    Endpoint description here.

    Explain what this endpoint does, what parameters it accepts,
    and what it returns.
    """
    url = f"{BASE_URL}/path/to/endpoint"

    # Build request parameters
    params = {"api_key": API_KEY}
    if param1:
        params["param1"] = param1

    # Make request
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"[API Name] failed: {r.text}")

    return r.json()


@router.post("/endpoint2")
async def post_endpoint2(
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_[apiname]_limit),
    body: dict = Body(..., description="Request payload"),
):
    """
    Another endpoint with POST method.
    """
    url = f"{BASE_URL}/path/to/endpoint2"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=headers, json=body)

    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"[API Name] failed: {r.text}")

    return r.json()
```

**Authentication Patterns**:

Choose the pattern that matches your API:

```python
# 1. API Key in query parameter
params = {"api_key": API_KEY, "other_param": value}
r = await client.get(url, params=params)

# 2. API Key in header
headers = {"API-Key": API_KEY}
r = await client.get(url, headers=headers)

# 3. Bearer token
headers = {"Authorization": f"Bearer {API_KEY}"}
r = await client.get(url, headers=headers)

# 4. Basic auth
from httpx import BasicAuth
auth = BasicAuth(username, password)
r = await client.get(url, auth=auth)
```

**Checklist**:
- [ ] Created `app/routes/[apiname].py`
- [ ] Imported all required modules
- [ ] Set up router with correct prefix and tags
- [ ] Retrieved API key using `get_key("[apiname]")`
- [ ] Created `APIRateLimiter` instance
- [ ] Implemented main endpoints with:
  - [ ] User authentication (`get_current_user`)
  - [ ] User rate limiting (`check_user_rate_limit`)
  - [ ] API rate limiting (`check_[apiname]_limit`)
  - [ ] Proper error handling
  - [ ] Docstrings explaining functionality
- [ ] Used `httpx.AsyncClient` for HTTP requests
- [ ] Set appropriate timeout values (10-15 seconds recommended)
- [ ] Handled different response status codes

---

### Step 4: Register Router in `app/main.py`

**File**: `D:\02_ApiServer\app\main.py`

**4a. Import the router** (around line 24):

```python
from app.routes.pushcut import router as pushcut_router
from app.routes.[apiname] import router as [apiname]_router  # ← Add this
```

**4b. Include the router** (around line 134):

```python
app.include_router(pushcut_router)
app.include_router([apiname]_router)  # ← Add this
app.include_router(software_router)
```

**4c. Update FastAPI description** (around line 32):

```python
app = FastAPI(
    title="API Gateway",
    description="Centralized API proxy with rate limiting for weather, geocoding, location, telephone directory, NASA space data, Open Library book services, iOS automation (Pushcut), and [Your New API] | © 2026 JestingDart4369",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
```

**Checklist**:
- [ ] Imported router at top of file
- [ ] Registered router with `app.include_router()`
- [ ] Updated FastAPI description to include new service
- [ ] Saved `app/main.py`

---

### Step 5: Database Seeding

The API configuration will be **automatically seeded** into the `api_config` table on next server restart (if the table is empty).

**If your database already has data**:

**Option A**: Add manually via API (recommended):
```bash
curl -X POST "http://localhost:8080/settings/apis" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_name": "[apiname]",
    "is_active": true,
    "max_calls_per_hour": 1000
  }'
```

**Option B**: Reset database (destroys all data):
```bash
# Backup first!
cp data/gateway.db data/gateway.db.backup

# Delete and restart (will re-seed from .env)
rm data/gateway.db
docker compose restart
```

**Checklist**:
- [ ] Understood database seeding process
- [ ] Chosen seeding method (auto / manual / reset)
- [ ] If manual: executed API call to add config

---

### Step 6: Test the Integration

**6a. Restart the server**:

```bash
# Docker
docker compose restart

# Local development
# Press Ctrl+C and re-run:
uvicorn app.main:app --reload --port 8080
```

**6b. Login and get token**:

```bash
TOKEN=$(curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your-username","password":"your-password"}' \
  | jq -r '.access_token')

echo $TOKEN  # Verify token was received
```

**6c. Test endpoints**:

```bash
# Test endpoint 1
curl "http://localhost:8080/[apiname]/endpoint1?param=value" \
  -H "Authorization: Bearer $TOKEN"

# Test endpoint 2
curl -X POST "http://localhost:8080/[apiname]/endpoint2" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

**6d. Verify in API docs**:

Visit: http://localhost:8080/docs

- [ ] New API section appears in sidebar
- [ ] All endpoints are listed
- [ ] Can test endpoints via "Try it out"

**6e. Check rate limiting**:

```bash
# Verify rate limit headers are present
curl -v "http://localhost:8080/[apiname]/endpoint1" \
  -H "Authorization: Bearer $TOKEN" 2>&1 | grep -i "X-RateLimit"

# Expected headers:
# X-RateLimit-Limit: 1000
# X-RateLimit-Remaining: 999
# X-RateLimit-Reset: <timestamp>
```

**Checklist**:
- [ ] Server restarted successfully
- [ ] Can obtain JWT token
- [ ] All endpoints return successful responses
- [ ] Endpoints appear in `/docs`
- [ ] Rate limit headers present in responses
- [ ] Invalid requests return proper error codes (400, 401, etc.)

---

### Step 7: Update Documentation

Update the following files to document your new API:

**7a. Update `CLAUDE.md`** (around line 30):

```markdown
├── routes/
    ├── weather.py      # GET /weather, /weather/forecast/...
    ├── geo.py          # GET /geo/geocode, /geo/ip
    ├── [apiname].py    # GET /[apiname]/... ← Add this
```

**7b. Add to "Adding New Proxy Endpoints" section** (around line 180):

```markdown
### Available APIs

- **Weather** (OpenWeather): Current weather and forecasts
- **Geocoding** (Geoapify): Address to coordinates
- **IP Location** (IPRegistry): IP geolocation
- **Email** (Resend): Send emails
- **Telephone** (search.ch): Swiss directory
- **NASA**: Space images and data
- **Library** (Open Library): Book search and metadata
- **Pushcut**: iOS automation and notifications
- **[Your API]**: [Brief description] ← Add this
```

**7c. Add test commands to `CLAUDE.md`** (around line 200):

```markdown
# --- [Your API Name] ---
curl "http://localhost:8080/[apiname]/endpoint1?param=value" \
  -H "Authorization: Bearer <TOKEN>"
```

**7d. Update `README.md`**:

Add your API to the features list and usage examples.

**Checklist**:
- [ ] Updated `CLAUDE.md` with route info
- [ ] Added API to features list
- [ ] Added test commands
- [ ] Updated `README.md`
- [ ] Committed documentation changes

---

## Rollback Instructions

If something goes wrong, you can rollback the changes:

### Quick Rollback (Keep Database):

```bash
# 1. Revert code changes
git diff HEAD  # Review changes
git checkout -- .env app/config.py app/routes/[apiname].py app/main.py

# 2. Restart server
docker compose restart
```

### Full Rollback (Reset Database):

```bash
# 1. Restore database backup
cp data/gateway.db.backup data/gateway.db

# 2. Revert code
git checkout -- .env app/config.py app/routes/[apiname].py app/main.py

# 3. Restart
docker compose restart
```

### Remove API from Active Database:

```bash
# Disable the API
curl -X PUT "http://localhost:8080/settings/apis/[apiname]" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Or delete it (Root only)
curl -X DELETE "http://localhost:8080/settings/apis/[apiname]" \
  -H "Authorization: Bearer <ROOT_TOKEN>"
```

---

## Troubleshooting

### Server won't start

```bash
# Check logs
docker compose logs api-gateway

# Common issues:
# - Missing .env variable → Add it
# - Syntax error in route file → Check Python syntax
# - Import error → Verify all imports are correct
# - Duplicate router registration → Check main.py
```

### Endpoint returns 503

```bash
# Check if API is enabled
curl "http://localhost:8080/settings/apis/[apiname]" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

# Enable it
curl -X PUT "http://localhost:8080/settings/apis/[apiname]" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

### Endpoint returns 502

- Check external API is accessible
- Verify API key is correct in `.env`
- Check API base URL
- Increase timeout in `httpx.AsyncClient(timeout=XX)`

### Rate limit always returns 429

```bash
# Check API's max_calls_per_hour
curl "http://localhost:8080/settings/apis/[apiname]" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

# Increase limit (superAdmin+)
curl -X PUT "http://localhost:8080/settings/apis/[apiname]" \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"max_calls_per_hour": 5000}'
```

---

## Example: Real Integration (Pushcut)

Here's how the Pushcut API was integrated as a complete example:

### 1. Environment Variables (`.env`):
```env
PUSHCUT_KEY=your_pushcut_api_key_here
PUSHCUT_ENABLED=true
PUSHCUT_MAX_CALLS=1000
```

### 2. API Registry (`app/config.py`):
```python
"pushcut": "PUSHCUT",
```

### 3. Route File (`app/routes/pushcut.py`):
- 7 endpoints implemented
- Authentication via `API-Key` header
- Base URL: `https://api.pushcut.io/v1`

### 4. Router Registration (`app/main.py`):
```python
from app.routes.pushcut import router as pushcut_router
app.include_router(pushcut_router)
```

### 5. Testing:
```bash
curl "http://localhost:8080/pushcut/devices" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Checklist Summary

Use this quick checklist to track your progress:

- [ ] **Prerequisites**: Gathered API docs, key, base URL, rate limits
- [ ] **Step 1**: Added 3 env vars to `.env`
- [ ] **Step 2**: Added API to `API_REGISTRY` in `app/config.py`
- [ ] **Step 3**: Created route file `app/routes/[apiname].py`
- [ ] **Step 4**: Registered router in `app/main.py` (import + include + description)
- [ ] **Step 5**: Database seeding (auto/manual/reset)
- [ ] **Step 6**: Tested all endpoints
- [ ] **Step 7**: Updated documentation (CLAUDE.md, README.md)
- [ ] **Final**: Committed changes to git

---

## Need Help?

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **httpx Docs**: https://www.python-httpx.org/
- **Project Issues**: https://github.com/JestingDart4369/ApiServer_Novaroma/issues

---

**Template Version**: 1.0
**Last Updated**: 2026-02-08
**Maintainer**: JestingDart4369
