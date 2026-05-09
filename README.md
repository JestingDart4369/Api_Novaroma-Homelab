# API Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com)

**Centralized API Gateway for Weather, Geocoding, Location, Email, Telephone Directory, NASA Space Data, Open Library Book Services, and Software & Hardware Health Monitoring**

A production-ready FastAPI gateway with 4-level role-based access control and comprehensive rate limiting that proxies external APIs while handling authentication server-side. All provider API keys are stored securely on the server — clients never see them.

🌐 **[Live Documentation](https://api.novaroma-homelab.uk)** | 📚 **[API Docs](https://api.novaroma-homelab.uk/docs)** | 🎯 **[Wiki](../../wiki)**

---

## ✨ Features

- 🔐 **JWT Authentication** - Secure token-based access with 1-hour expiration
- 👥 **4-Level RBAC** - user → admin → superAdmin → Root with fine-grained permissions
- ⚡ **Rate Limiting** - Per-user (role-based) and per-API quotas, live-editable via admin endpoints
- 🌦️ **Weather API** - Current weather, hourly & daily forecasts (OpenWeather)
- 📍 **Location Services** - Geocoding (Geoapify) & IP geolocation (IPRegistry)
- 📞 **Telephone Directory** - Swiss telephone search (search.ch)
- 🚀 **NASA APIs** - Astronomy Picture of the Day & Earth satellite imagery (EPIC)
- 📚 **Open Library** - Book search, details, covers, authors, subjects, and Internet Archive S3
- 📧 **Email Service** - Send emails via Resend with simplified addressing
- 💻 **Software Health** - Push-based health monitoring: your apps call in their own status
- 🖥️ **Hardware Health** - Same as above, plus free-form config per device (IP, firmware, etc.)
- 🔔 **Server Notifications** - Automatic email alerts for errors and startup events
- 🔒 **Input Validation** - Comprehensive security validation on all endpoints
- 📝 **Audit Logging** - All user actions logged for security monitoring
- ⚙️ **Live Settings** - Toggle APIs, adjust rate limits, manage users — no restart needed
- 🐳 **Docker Ready** - Complete containerization with Docker Compose
- ☁️ **Cloudflare Tunnel** - Secure public access without port forwarding
- 📊 **Auto Documentation** - Interactive API docs with Swagger UI & ReDoc
- 🗄️ **SQLite Database** - Lightweight user and config management with SQLAlchemy ORM

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Cloudflare account (for public access)
- API keys:
  - OpenWeather (weather and forecasts)
  - Geoapify (geocoding)
  - IPRegistry (IP geolocation)
  - Resend (email service)
  - search.ch (Swiss telephone directory, optional)
  - NASA (space data, free tier available)
  - Internet Archive S3 (Open Library covers, optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/JestingDart4369/ApiServer_Novaroma.git
   cd ApiServer_Novaroma
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and fill in your API keys and credentials
   ```

3. **Start the gateway**
   ```bash
   docker compose up -d --build
   ```

4. **Verify it's running**
   ```bash
   curl http://localhost:8080/health
   # Should return: {"ok": true}
   ```

5. **Access documentation**
   - Homepage: http://localhost:8080
   - API Docs: http://localhost:8080/docs
   - ReDoc: http://localhost:8080/redoc

---

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure. All API keys follow a consistent pattern: `{PREFIX}_KEY`, `{PREFIX}_ENABLED`, `{PREFIX}_MAX_CALLS`.

#### Core
| Variable | Description | Required |
|----------|-------------|----------|
| `JWT_SECRET` | Secret key for JWT tokens | ✅ |
| `BOOTSTRAP_ADMIN_USERNAME` | Initial Root user username (first run only) | ✅ |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial Root user password (first run only) | ✅ |

#### API Keys & Settings
| Prefix | Service | Notes |
|--------|---------|-------|
| `OPENWEATHER` | Weather + forecasts | Required |
| `GEOAPIFY` | Geocoding | Required |
| `IPREGISTRY` | IP geolocation | Required |
| `RESEND` | Email sending | Required |
| `TELEPHONE` | Swiss telephone directory | Optional |
| `NASA` | APOD + EPIC satellite images | Free tier available |
| `OPENLIBRARY` | Books + Internet Archive S3 | Also needs `OPENLIBRARY_SECRET` |

#### Role Rate Limits
| Variable | Default | Role |
|----------|---------|------|
| `ROLE_USER_MAX_CALLS` | 1000 | user |
| `ROLE_ADMIN_MAX_CALLS` | 2000 | admin |
| `ROLE_SUPERADMIN_MAX_CALLS` | 5000 | superAdmin |
| `ROLE_ROOT_MAX_CALLS` | 10000 | Root |

#### Email & Deployment
| Variable | Description | Required |
|----------|-------------|----------|
| `DEFAULT_FROM_EMAIL` | Default sender for client emails | ✅ |
| `SERVER_FROM_EMAIL` | Sender for server alert emails | ✅ |
| `ADMIN_EMAIL` | Receives server alerts | ✅ |
| `EMAIL_DOMAIN` | Domain for recipients in `/email/send-simple` | ✅ |
| `SENDER_DOMAIN` | Verified domain for senders (must be verified in Resend) | ✅ |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel token | Optional |
| `DB_URL` | SQLAlchemy DB URL (defaults to `./data/gateway.db`) | Optional |

**⚠️ NEVER commit `.env` to Git!** It's already in `.gitignore`.

---

## 📖 Usage

### Authentication

Get an access token:

```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your-username","password":"your-password"}'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Making Authenticated Requests

Use the token in the `Authorization` header:

```bash
curl "http://localhost:8080/weather?city=London" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### API Endpoints

**Authentication**
- `POST /auth/login` - Get JWT access token

**Weather** (OpenWeather)
- `GET /weather?city=London` - Current weather
- `GET /weather/forecast/hourly?lat=51.5074&lon=-0.1278` - 48-hour forecast
- `GET /weather/forecast/daily?lat=51.5074&lon=-0.1278&cnt=7` - 7-day forecast

**Location**
- `GET /geo/geocode?text=London` - Convert city to coordinates (Geoapify)
- `GET /geo/ip` - Get location from your IP (IPRegistry)

**Telephone Directory**
- `GET /telephone/search?was=name&wo=city` - Swiss telephone search (search.ch)

**NASA**
- `GET /nasa/apod` - Astronomy Picture of the Day
- `GET /nasa/epic/{collection}` - Earth satellite images (natural or enhanced)
- `GET /nasa/epic/{collection}/available` - Available EPIC dates

**Library** (Open Library + Internet Archive)
- `GET /library/search?q=query` - Search books, authors, works
- `GET /library/books?bibkeys=ISBN:...` - Get book details
- `GET /library/covers/{type}/{id}` - Get book covers
- `GET /library/works/{work_id}` - Get work information
- `GET /library/authors/{id}` - Get author information
- `GET /library/subjects/{subject}` - Get books by subject
- `GET /library/archive/*` - Internet Archive S3 API

**Email**
- `POST /email/send` - Send email (full control over sender/recipients)
- `POST /email/send-simple` - Send email (domain pre-configured, simplified)

**Software Health**
- `GET /software` - List all registered software with health status
- `GET /software/{name}` - Health for one software (includes `stale` flag if no heartbeat in 5 min)
- `POST /software/{name}/heartbeat` - Software pushes `{"health":"ok","details":{...}}`

**Hardware Health**
- `GET /hardware` - List all registered hardware with health + config
- `GET /hardware/{name}` - Health + config for one device (includes `stale` flag)
- `POST /hardware/{name}/heartbeat` - Device pushes `{"health":"ok","config":{...},"details":{...}}`

**Rate Limits**
- `GET /rate-limits/me` - Your current rate limit status
- `GET /rate-limits/apis` - All API quota statuses
- `GET /rate-limits/all` - Full rate limit overview (admin+)

**Settings** (admin+ unless noted)
- `GET /settings/users` - List all users
- `POST /settings/users` - Create user
- `POST /settings/users/{id}/enable` - Enable user
- `POST /settings/users/{id}/disable` - Disable user
- `PUT /settings/users/{id}` - Change role/password (superAdmin+)
- `DELETE /settings/users/{id}` - Delete user (Root only)
- `GET /settings/apis` - List all API configs
- `GET /settings/apis/{name}` - Get single API config
- `PUT /settings/apis/{name}` - Toggle API / change limit (superAdmin+)
- `GET /settings/roles` - List all role limits
- `PUT /settings/roles/{role}` - Change role limit (Root only)
- `GET /settings/software` - List all software entries
- `POST /settings/software` - Register new software (admin+)
- `PUT /settings/software/{name}` - Enable / disable (superAdmin+)
- `DELETE /settings/software/{name}` - Remove software (superAdmin+)
- `GET /settings/hardware` - List all hardware entries
- `POST /settings/hardware` - Register new device + optional config (admin+)
- `PUT /settings/hardware/{name}` - Update config / enable / disable (superAdmin+)
- `DELETE /settings/hardware/{name}` - Remove device (superAdmin+)

Full interactive documentation: https://api.novaroma-homelab.uk/docs

---

## 👥 Role-Based Access Control

| Role | Proxy APIs | User Management | API/Role Settings | Software & Hardware |
|------|-----------|-----------------|-------------------|---------------------|
| `user` | ✅ | ❌ | ❌ | Read health only |
| `admin` | ✅ | Create, list, enable/disable | View only | Register new entries |
| `superAdmin` | ✅ | All of above + change role/password | Toggle APIs, adjust limits | Update config, enable/disable, delete |
| `Root` | ✅ | All of above + delete users | All of above + change role limits | All of above |

The first user created at bootstrap is automatically assigned the `Root` role.

---

## ☁️ Cloudflare Tunnel Setup

1. Go to **Cloudflare Zero Trust** → **Networks** → **Tunnels**
2. Create a new tunnel → Select **Docker**
3. Copy the tunnel token to `.env` as `CLOUDFLARE_TUNNEL_TOKEN`
4. Add **Public Hostname**:
   - Subdomain: `api`
   - Domain: `your-domain.com`
   - Service: `http://api-gateway:8080`
5. Save and your gateway is now publicly accessible at `https://api.your-domain.com`

---

## 🏗️ Architecture

```
┌─────────────┐
│   Clients   │ (Python apps, web apps, mobile apps)
└──────┬──────┘
       │ HTTPS + JWT
       ▼
┌─────────────────────────────────────┐
│     Cloudflare Tunnel (Optional)    │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│        FastAPI API Gateway           │
│  ┌────────────────────────────────┐  │
│  │  JWT Auth (4-level RBAC)       │  │
│  │  Rate Limiting (user + API)    │  │
│  │  Input Validation              │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  Proxy Routes                  │  │
│  │  /weather   /nasa              │  │
│  │  /geo       /library           │  │
│  │  /telephone /email             │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  Health Monitoring             │  │
│  │  /software  /hardware          │  │
│  │  (push heartbeats → DB)        │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  Admin: /settings              │  │
│  │  /users /apis /roles           │  │
│  │  /software  /hardware          │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  SQLite: users, api_config,    │  │
│  │  role_limits, software,        │  │
│  │  hardware                      │  │
│  └────────────────────────────────┘  │
└──────────┬───────────────────────────┘
           │ Server-side API keys
           ▼
┌────────────────────────────────────────┐
│     External APIs (Keys Hidden)        │
│  OpenWeather • Geoapify • IPRegistry   │
│  search.ch • NASA • Open Library       │
│             Resend                     │
└────────────────────────────────────────┘
```

---

## 🛡️ Security

- ✅ **API keys stored server-side only** - Never exposed to clients
- ✅ **Password hashing** - bcrypt with SHA-256 pre-hash for long passwords
- ✅ **JWT tokens** - Expire after 1 hour
- ✅ **4-level RBAC** - user / admin / superAdmin / Root with clear permission boundaries
- ✅ **Rate limiting** - Per-user (role-based) and per-API quotas
- ✅ **Input validation** - Comprehensive validation on all endpoints
- ✅ **Audit logging** - All user actions logged for security
- ✅ **Self-modification guards** - Users cannot disable or delete their own account
- ✅ **Environment isolation** - All secrets in `.env` (gitignored)
- ✅ **Email alerts** - Admin notified of startup failures and critical errors

---

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Full developer reference (structure, patterns, env vars)
- **[RATE_LIMITING.md](RATE_LIMITING.md)** - Comprehensive rate limiting guide
- **[SECURITY.md](SECURITY.md)** - Security policy and best practices
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[.env.example](.env.example)** - Environment configuration template
- **[Wiki](../../wiki)** - Detailed guides and tutorials
- **[API Reference](https://api.novaroma-homelab.uk/docs)** - Interactive Swagger UI

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**JestingDart4369**

- GitHub: [@JestingDart4369](https://github.com/JestingDart4369)

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [OpenWeather](https://openweathermap.org/) - Weather data
- [Geoapify](https://www.geoapify.com/) - Geocoding services
- [IPRegistry](https://ipregistry.co/) - IP geolocation
- [search.ch](https://tel.search.ch/) - Swiss telephone directory
- [NASA](https://api.nasa.gov/) - Space and astronomy data
- [Open Library](https://openlibrary.org/) - Book data and covers
- [Resend](https://resend.com/) - Email API
- [Cloudflare](https://www.cloudflare.com/) - Tunnel infrastructure

---

## 📊 Project Status

🟢 **Production Ready** - Live at https://api.novaroma-homelab.uk

**Current state:**
- ⚡ 4-level role-based access control (user / admin / superAdmin / Root)
- ⚡ Per-user and per-API rate limiting with live admin controls
- 💻 Push-based health monitoring for software and hardware (stale detection, free-form config)
- 📞 Swiss telephone directory integration
- 🚀 NASA APOD + EPIC satellite imagery
- 📚 Open Library book search + Internet Archive S3
- 🔒 Input validation, audit logging, self-modification guards
- ⚙️ Live settings panel (/settings) — no restart needed for config changes

Built with love by JestingDart4369
