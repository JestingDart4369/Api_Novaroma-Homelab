## API Gateway (FastAPI + JWT + SQLite + Docker + Cloudflare Tunnel)

### Setup
1) Copy `.env.example` to `.env` and fill values:
- CLOUDFLARE_TUNNEL_TOKEN
- JWT_SECRET
- OPENWEATHER_KEY
- GEOAPIFY_KEY
- BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD

2) Start:
```bash
docker compose up -d --build
docker compose logs -f api-gateway
docker compose logs -f cloudflared
```

### Cloudflare

Zero Trust -> Tunnels -> Create Tunnel -> Docker -> copy token to .env.
Add Public Hostname:
- api.yourdomain.com
- Service: http://api-gateway:8080

### Test

Health:
- http://localhost:8080/health
- https://api.yourdomain.com/health

Login:
```bash
curl -X POST https://api.yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"eric","password":"ChangeThisPasswordNow"}'
```

Use token:
```bash
curl "https://api.yourdomain.com/weather?city=Zurich" \
  -H "Authorization: Bearer <TOKEN>"
```

Admin: create user:
```bash
curl -X POST "https://api.yourdomain.com/users" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123","role":"user"}'
```

---

## Cloudflare side (what must be configured)
In Cloudflare Zero Trust:
1. **Create Tunnel** -> choose **Docker** -> copy token into `.env`
2. **Public Hostname**:
   - Hostname: `api.yourdomain.com`
   - Service: `http://api-gateway:8080`
3. (Recommended) Add **Access** policy so only you can reach it:
   - Access -> Applications -> Self-hosted
   - Domain: `api.yourdomain.com`
   - Policy allow only your email / account

---

## API summary (endpoints)
Public:
- `GET /health`

Auth:
- `POST /auth/login` -> `{access_token, token_type}`

Protected (Bearer JWT):
- `GET /weather?city=...`
- `GET /geocode?text=...`

Admin-only:
- `POST /users` create
- `GET /users` list
- `POST /users/{id}/disable`
- `POST /users/{id}/enable`

---

## Commands
```bash
# build/run
docker compose up -d --build

# view logs
docker compose logs -f api-gateway
docker compose logs -f cloudflared

# stop
docker compose down
```
