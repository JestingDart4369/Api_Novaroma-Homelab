# Rate Limiting Documentation

## Overview

The API Gateway implements comprehensive rate limiting to:
- Protect server resources from abuse
- Ensure fair usage across all users
- Prevent exhausting external API quotas
- Maintain service availability for all clients

## Rate Limit Types

### 1. Per-User Rate Limits

Rate limits are applied per authenticated user based on their role:

| Role | Requests per Hour |
|------|-------------------|
| Regular User | 1,000 |
| Admin User | 5,000 |

These limits apply across ALL API endpoints that require authentication.

### 2. Per-API Rate Limits

To protect external API quotas, each upstream API has its own rate limit (shared across all users):

| API Service | Requests per Hour | Notes |
|-------------|-------------------|-------|
| NASA | 900 | Free tier: 1000/hour (90% safety margin) |
| OpenWeather | 3,000 | ~60/min typical limit |
| Geoapify | 5,000 | Generous free tier |
| IPRegistry | 10,000 | High free tier |
| Resend Email | 100 | Conservative limit for email |
| Telephone (search.ch) | 1,000 | Reasonable default |
| Open Library | 5,000 | Public API, generous limit |

## How Rate Limiting Works

### Request Flow

1. User makes authenticated API request
2. System checks user's personal rate limit
3. System checks the target API's quota
4. If both checks pass, request proceeds
5. If either limit is exceeded, returns HTTP 429

### Rate Limit Window

- All rate limits use a **sliding 1-hour window**
- Counters reset at the start of each hour (UTC)
- Old entries are automatically cleaned up every 5 minutes

### Response Headers

All API responses include rate limit information in headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1706745600
```

- `X-RateLimit-Limit`: Total requests allowed per hour
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## HTTP 429 Response

When a rate limit is exceeded, the API returns:

**Status Code:** `429 Too Many Requests`

**Headers:**
```
Retry-After: 3600
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1706745600
```

**Body:**
```json
{
  "detail": "Rate limit exceeded. Try again in 3600 seconds."
}
```

## Checking Rate Limit Status

### Get Your Current Status

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  https://api.novaroma-homelab.uk/rate-limits/me
```

**Response:**
```json
{
  "user_id": 1,
  "username": "john",
  "role": "user",
  "limit_per_hour": 1000,
  "remaining": 847,
  "reset_timestamp": 1706745600,
  "status": "ok"
}
```

### Get API Quota Status

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  https://api.novaroma-homelab.uk/rate-limits/api
```

**Response:**
```json
{
  "apis": {
    "nasa": {
      "limit_per_hour": 900,
      "remaining": 743,
      "reset_timestamp": 1706745600,
      "status": "ok"
    },
    "openweather": {
      "limit_per_hour": 3000,
      "remaining": 2456,
      "reset_timestamp": 1706745600,
      "status": "ok"
    }
  }
}
```

### Get All Rate Limits (Admin Only)

```bash
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  https://api.novaroma-homelab.uk/rate-limits/all
```

Returns comprehensive statistics on all users and API usage.

## Best Practices

### For API Clients

1. **Monitor Headers**: Always check `X-RateLimit-Remaining` in responses
2. **Handle 429s**: Implement exponential backoff when rate limited
3. **Use Retry-After**: Respect the `Retry-After` header value
4. **Batch Requests**: Combine multiple operations when possible
5. **Cache Results**: Cache responses to reduce API calls

### Example: Handling Rate Limits in Python

```python
import httpx
import time

def make_request_with_retry(url, headers, max_retries=3):
    """Make API request with automatic retry on rate limit"""
    for attempt in range(max_retries):
        response = httpx.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()

        elif response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Retrying in {retry_after} seconds...")
            time.sleep(retry_after)

        else:
            response.raise_for_status()

    raise Exception("Max retries exceeded")
```

### Example: Monitoring Rate Limits

```python
import httpx

def check_rate_limit_status(token):
    """Check your current rate limit status"""
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.get(
        "https://api.novaroma-homelab.uk/rate-limits/me",
        headers=headers
    )

    data = response.json()
    remaining = data['remaining']
    limit = data['limit_per_hour']

    print(f"Rate limit: {remaining}/{limit} requests remaining")

    if remaining < 100:
        print("WARNING: Running low on requests!")

    return data
```

## Rate Limit Bypass (Not Supported)

Rate limits **cannot be bypassed** or increased on a per-request basis. If you need higher limits:

1. **Regular Users**: Contact admin to upgrade to admin role
2. **Admin Users**: Limits are already set at maximum
3. **API Quotas**: These protect external services and cannot be increased

## Technical Details

### Implementation

- **Storage**: In-memory dictionary with thread-safe locks
- **Cleanup**: Automatic removal of entries older than 2 hours
- **Granularity**: Hourly buckets (YYYY-MM-DD-HH)
- **Dependencies**: FastAPI native, no external rate limit libraries

### Architecture

```
Request → Authentication → User Rate Check → API Rate Check → Upstream API
                ↓                 ↓                  ↓
             JWT Token      Per-User Limit    Per-API Quota
```

### Performance

- **Overhead**: ~1-2ms per request
- **Memory**: ~50KB per 1000 active users
- **Scalability**: Suitable for small-to-medium deployments

For high-scale deployments, consider migrating to Redis-backed rate limiting.

## Monitoring and Logging

### Log Messages

Rate limit violations are logged with:

```
WARNING: User rate limit exceeded: user_id=123, role=user
WARNING: API rate limit exceeded: api=nasa
```

### Admin Monitoring

Admins can view real-time usage:

```bash
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  https://api.novaroma-homelab.uk/rate-limits/all
```

This shows:
- Per-user request counts
- Per-API quota usage
- Hourly breakdown of requests

## Troubleshooting

### Problem: Getting 429 Too Many Requests

**Solutions:**
1. Check your rate limit status: `GET /rate-limits/me`
2. Wait for reset time (see `X-RateLimit-Reset` header)
3. Reduce request frequency
4. Implement caching in your client
5. Contact admin if you need higher limits

### Problem: API Quota Exceeded

**Solutions:**
1. Check API status: `GET /rate-limits/api`
2. This affects ALL users - wait for reset
3. Use alternative endpoints if available
4. Spread requests across multiple hours

### Problem: Incorrect Rate Limit Counts

**Solutions:**
1. Rate limits use UTC time - check timezone
2. Counters reset at start of each hour
3. Wait 5 minutes for automatic cleanup
4. Contact admin if persistent issues

## Future Enhancements

Planned improvements:

- [ ] Redis backend for distributed deployments
- [ ] Per-endpoint rate limits (in addition to per-user)
- [ ] Custom rate limit tiers (bronze/silver/gold users)
- [ ] Rate limit burst allowance
- [ ] Webhook alerts for approaching limits
- [ ] Grafana dashboard for usage metrics

## Security Considerations

- Rate limits are enforced AFTER authentication
- Cannot bypass by changing IP address
- JWT tokens required for all rate-limited endpoints
- Admin role required for viewing global statistics
- Rate limit data stored in-memory (not persisted)

## Configuration

Rate limits are defined in `app/rate_limit.py`:

```python
# Per-user limits
USER_RATE_LIMITS = {
    "user": 1000,
    "admin": 5000,
}

# Per-API limits
API_RATE_LIMITS = {
    "nasa": 900,
    "openweather": 3000,
    # ...
}
```

To modify limits, edit these values and restart the server.

## Support

For rate limit issues or questions:

1. Check this documentation
2. Review API response headers
3. Use `/rate-limits/me` endpoint
4. Contact system administrator
5. Submit issue on GitHub

---

**Last Updated:** 2026-01-30
**Version:** 1.0.0
