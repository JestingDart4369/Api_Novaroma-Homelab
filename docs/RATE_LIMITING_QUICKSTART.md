# Rate Limiting Quick Start Guide

## TL;DR

The API Gateway now has rate limiting. Your users get 1000 requests/hour, admins get 5000/hour. Each external API also has its own quota.

## For API Users

### Check Your Status
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.novaroma-homelab.uk/rate-limits/me
```

### Response Headers (on every API call)
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1706745600
```

### When Rate Limited (HTTP 429)
```json
{
  "detail": "Rate limit exceeded. Try again in 3600 seconds."
}
```

Wait for the `Retry-After` header value (in seconds).

## For Developers

### Adding Rate Limits to New Endpoints

```python
from fastapi import APIRouter, Depends
from app.security import get_current_user
from app.rate_limit import check_user_rate_limit, check_nasa_limit

@router.get("/nasa/apod")
async def apod(
    user: User = Depends(get_current_user),
    _rate_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_nasa_limit)
):
    """
    Rate Limits:
    - User: 1000 req/hour (regular), 5000 req/hour (admin)
    - NASA API: 900 req/hour (shared across all users)
    """
    # Your code here
```

### Available API Limiters

```python
from app.rate_limit import (
    check_nasa_limit,
    check_openweather_limit,
    check_geoapify_limit,
    check_ipregistry_limit,
    check_resend_limit,
    check_telephone_limit,
    check_openlibrary_limit,
)
```

### Creating Custom API Limiter

```python
from app.rate_limit import get_api_limiter

check_myapi_limit = get_api_limiter("myapi")
```

First, add to `app/rate_limit.py`:
```python
API_RATE_LIMITS = {
    # ... existing ...
    "myapi": 2000,  # 2000 requests/hour
}
```

## Rate Limit Configuration

File: `app/rate_limit.py`

```python
# Per-user limits (requests per hour)
USER_RATE_LIMITS = {
    "user": 1000,
    "admin": 5000,
}

# Per-API limits (requests per hour per API)
API_RATE_LIMITS = {
    "nasa": 900,
    "openweather": 3000,
    "geoapify": 5000,
    "ipregistry": 10000,
    "resend": 100,
    "telephone": 1000,
    "openlibrary": 5000,
}
```

## Testing

Run the test suite:
```bash
python test_rate_limit.py
```

## Client Code Example

### Python Client with Retry
```python
import httpx
import time

def api_call_with_retry(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = httpx.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
        else:
            response.raise_for_status()

    raise Exception("Max retries exceeded")
```

### Check Before Calling
```python
def check_rate_limit(token):
    response = httpx.get(
        "https://api.novaroma-homelab.uk/rate-limits/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()

    if data['remaining'] < 10:
        print("WARNING: Only", data['remaining'], "requests remaining!")

    return data['remaining']
```

## Troubleshooting

### Getting 429 Errors?
1. Check `/rate-limits/me` to see your status
2. Wait for reset time (see `X-RateLimit-Reset` header)
3. Implement exponential backoff
4. Cache responses to reduce API calls

### Need Higher Limits?
- Regular users: Contact admin to upgrade to admin role
- Admin users: Limits are already at maximum
- API quotas: These protect external services and cannot be increased

### Rate Limit Not Working?
1. Verify authentication works (JWT token required)
2. Check server logs for errors
3. Ensure middleware is loaded in `main.py`
4. Run `python test_rate_limit.py` to verify logic

## Monitoring (Admin Only)

```bash
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  https://api.novaroma-homelab.uk/rate-limits/all
```

Shows:
- All users' request counts
- All APIs' quota usage
- Hourly breakdown

## Key Files

- `app/rate_limit.py` - Core rate limiting logic
- `app/routes/rate_limits.py` - Monitoring endpoints
- `RATE_LIMITING.md` - Full documentation
- `test_rate_limit.py` - Test suite

## Common Patterns

### Pattern 1: Simple Endpoint (User Limit Only)
```python
@router.get("/simple")
async def simple(
    user: User = Depends(get_current_user),
    _rate_limit: dict = Depends(check_user_rate_limit)
):
    return {"message": "Hello"}
```

### Pattern 2: Endpoint with External API (Both Limits)
```python
@router.get("/weather")
async def weather(
    city: str,
    user: User = Depends(get_current_user),
    _rate_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_openweather_limit)
):
    # Call OpenWeather API
    return data
```

### Pattern 3: Admin Endpoint (Admin + Rate Limit)
```python
@router.delete("/delete")
async def delete(
    user: User = Depends(require_admin),
    _rate_limit: dict = Depends(check_user_rate_limit)
):
    # Only admins can access
    return {"status": "deleted"}
```

## FAQ

**Q: Do rate limits reset at midnight?**
A: No, they reset every hour (e.g., 14:00, 15:00, 16:00 UTC)

**Q: Can I see other users' rate limits?**
A: No (unless you're admin using `/rate-limits/all`)

**Q: What happens if API quota is exhausted?**
A: All users get HTTP 429 until the quota resets

**Q: Are rate limits per IP or per user?**
A: Per authenticated user (based on JWT token)

**Q: Can I bypass rate limits?**
A: No. They're enforced server-side and cannot be bypassed.

## Need More Info?

See `RATE_LIMITING.md` for comprehensive documentation.

---

**Quick Reference Card**

```
┌─────────────────────────────────────────────────────┐
│ RATE LIMITS AT A GLANCE                             │
├─────────────────────────────────────────────────────┤
│ Regular User: 1000 req/hour                         │
│ Admin User:   5000 req/hour                         │
│                                                      │
│ NASA:         900 req/hour (all users)              │
│ OpenWeather:  3000 req/hour (all users)             │
│ Email:        100 req/hour (all users)              │
│                                                      │
│ Check Status: GET /rate-limits/me                   │
│ Headers:      X-RateLimit-Limit/Remaining/Reset     │
│ On Limit:     HTTP 429 + Retry-After header         │
└─────────────────────────────────────────────────────┘
```
