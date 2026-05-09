# Client SDK for Hardware

**CPython template for building gateway-connected hardware clients.**

Copy this folder, fill in `config.py`, run `main.py`. Heartbeat and config sync work out of the box.

---

## Quick Start

### 1. Copy SDK

```bash
cp -r tools/client_sdk_hardware/ ~/my-hardware-project/
cd ~/my-hardware-project/
```

### 2. Fill Config

Edit `config.py`:

```python
GATEWAY_URL      = "https://api.novaroma-homelab.uk"
GATEWAY_USERNAME = "my-device-user"
GATEWAY_PASSWORD = "secret"
HARDWARE_NAME    = "my-device"

BOOT_TIMEOUT  = 10      # seconds: max wait for network
HB_INTERVAL   = 30      # seconds between heartbeats
DISPLAY_ENABLED = True  # False for headless (suppresses stdout)
```

### 3. Register Hardware on Gateway

```bash
curl -X POST https://api.novaroma-homelab.uk/settings/hardware \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-device",
    "config": {"my_key": "my_value"}
  }'
```

### 4. Run

```bash
python main.py
```

Output:
```
[boot] Starting
[boot] Checking network
[boot] Network OK
[boot] Authenticated
[main] Heartbeat active, interval 30s  …  Ctrl-C to stop
[HB] ok
[HB] config: {'my_key': 'my_value'}
[HB] ok
...
```

---

## File Structure

| File | Purpose |
|------|---------|
| **config.py** | Gateway creds, hardware name, timings, display toggle |
| **gateway.py** | Full SDK: 50+ endpoints (weather, geo, NASA, library, email, health monitoring, admin settings) |
| **boot.py** | Network check + auth, returns warmed `GatewayClient` or `None` |
| **heartbeat.py** | Cooperative heartbeat (30s interval), config fetch |
| **main.py** | Entry point: `boot()` → `Heartbeat` loop (extend with your own logic) |
| **README.md** | This file |

---

## Architecture

```
boot()
  ├─ Check HARDWARE_NAME set
  ├─ Poll gateway host (TCP probe) until reachable or BOOT_TIMEOUT
  ├─ Authenticate (JWT login)
  └─ Return GatewayClient

main()
  ├─ gw = boot()
  ├─ hb = Heartbeat(gw, status=..., save=..., dbg=...)
  ├─ Load persisted config from settings.json
  └─ while True:
        hb.tick()       # fires heartbeat every HB_INTERVAL
        # your custom hardware logic here
        # update hb.health as needed ("ok", "warning", "error", "killed")
        time.sleep(1)
```

---

## Heartbeat Class

### Constructor

```python
hb = Heartbeat(gw, status=None, save=None, dbg=None)
```

- **gw** — GatewayClient from `boot()` (required)
- **status** — callable returning current status string (e.g. `lambda: "running"`)
- **save** — callable(dict) to persist state (merged into settings.json)
- **dbg** — callable(str) for logging (e.g. `_log` from boot.py)

### Properties

- **`.health`** — current health state: `"ok"`, `"warning"`, `"error"`, or `"killed"` (set directly)
- **`.config`** — last-fetched remote config dict (or `None`)
- **`.last_ping_ms`** — gateway response time in milliseconds (or `None` if last heartbeat failed)

### Methods

- **`.tick()`** — call every loop iteration; fires heartbeat when interval elapses
- **`.force()`** — fires heartbeat on next tick (ignores interval)

### Heartbeat POST

**Endpoint:** `POST /hardware/{HARDWARE_NAME}/heartbeat`

**Body:**
```json
{
  "health": "ok",         // or "warning", "error", "killed" (set via hb.health)
  "details": {
    "uptime": 12345.6,     // time.time()
    "status": "running"    // from status() callable
  }
}
```

**Error handling:**
- Network errors logged but heartbeat continues
- Device controls its own health state

### Config Fetch

**Endpoint:** `GET /settings/hardware`

Runs after every heartbeat POST.

**Extracts:** `(config, _)` for matching device

**Persistence:** if config changes → `save({"hw_config": new_config})`

---

## GatewayClient Full API

### Authentication

- **`_get_token()`** — returns cached token or logs in (auto-refresh at 55 min)

### Weather

- `get_weather(city, units="metric")` → current weather
- `get_hourly_forecast(lat, lon, units="metric")` → hourly forecast (48 hours)
- `get_daily_forecast(lat, lon, days=7, units="metric")` → daily forecast (7 days)

### Geo

- `geocode(city)` → lat/lon for city name
- `get_location_from_ip(ip=None)` → geo data for IP (or your IP if None)

### Telephone (Swiss directory)

- `telephone_search(was, wo)` → search by name + location

### NASA

- `nasa_apod(date=None, hd=False)` → Astronomy Picture of the Day
- `nasa_epic(collection="natural")` → EPIC images ("natural" or "enhanced")
- `nasa_epic_available(collection="natural")` → available dates

### Library (Open Library + Internet Archive)

- `library_search(q, limit=10)` → search books
- `library_books(bibkeys)` → book details
- `library_authors(author_id)` → author details
- `library_subjects(subject, limit=20)` → books by subject

### Email

- `send_email(to, subject, html, from_email=None)` → send email
- `send_email_simple(to_users, subject, html, from_name=None)` → simplified (domain from config)

### Health Monitoring

- `push_software_heartbeat(name, health, details=None)`
- `push_hardware_heartbeat(name, health, config=None, details=None)`
- `list_software()` → all software entries
- `get_software(name)` → one software entry
- `list_hardware()` → all hardware entries
- `get_hardware(name)` → one hardware entry

### Rate Limits

- `get_my_rate_limits()` → your current usage
- `get_api_rate_limits()` → all API quotas

### Settings (Admin+)

**Users:**
- `list_users()`
- `create_user(username, password, role="user")`
- `enable_user(user_id)` / `disable_user(user_id)`

**APIs:**
- `list_apis()`
- `set_api_active(api_name, active)`

**Roles:**
- `list_roles()`
- `set_role_active(role_name, active)`
- `set_role_limit(role_name, max_calls_per_hour)` (Root only)

**Software:**
- `list_software_settings()`
- `register_software(name)`

**Hardware:**
- `list_hardware_settings()`
- `get_hardware_config(name)` → `(config, is_active)` tuple
- `register_hardware(name, config=None)`
- `update_hardware_config(name, config)` (superAdmin+)

---

## Extending the SDK

### Add Custom Logic

Edit `main.py` loop body:

```python
while True:
    hb.tick()

    # your hardware logic here
    temperature = read_sensor()
    if temperature > 80:
        _log(f"[warn] High temp: {temperature}°C")
        hb.health = "warning"  # update health state
    else:
        hb.health = "ok"

    time.sleep(1)
```

### Push Custom Details

```python
def my_status():
    return f"temp={temperature}°C,fan={fan_speed}rpm"

hb = Heartbeat(gw, status=my_status, save=save_settings, dbg=_log)
```

Heartbeat details will include:
```json
{
  "uptime": 12345.6,
  "status": "temp=42°C,fan=1200rpm"
}
```

### Read Remote Config

```python
# After hb.tick() fetches config:
if hb.config:
    my_setting = hb.config.get("my_key", "default")
    _log(f"[config] my_key = {my_setting}")
```

Push config from gateway:
```bash
curl -X PUT https://api.novaroma-homelab.uk/settings/hardware/my-device \
  -H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"config": {"my_key": "new_value"}}'
```

Next heartbeat (within 30s) → `hb.config` updated.

---

## Settings Persistence

### Load

```python
from boot import load_settings

_settings = load_settings()  # reads settings.json
_my_state = _settings.get("my_state", 0)
```

### Save

```python
from boot import save_settings

save_settings({"my_state": 42})  # merges into settings.json
```

Heartbeat uses this for:
- `hw_config` — last-fetched remote config

You can add your own keys for application state.

---

## Headless Mode

Set `DISPLAY_ENABLED = False` in `config.py`.

**Effect:**
- All `_log()` calls suppressed (no stdout output)
- Boot progress hidden
- Heartbeat ticks silently

**Use case:** Server, router, headless Raspberry Pi, Docker container.

---

## Debugging

### Enable Logging

Set `DISPLAY_ENABLED = True` and `{"debug": true}` in settings.json.

**Output:**
```
[boot] Starting
[boot] Checking network
[boot] Network OK
[boot] Authenticated
[main] Heartbeat active, interval 30s
[HB] ok
[HB] config: {'my_key': 'my_value'}
[HB] ok
```

### Custom Debug

```python
from boot import _log

_log("[myapp] Starting sensor read")
temperature = read_sensor()
_log(f"[myapp] Temp: {temperature}°C")
```

Logs only print when `DISPLAY_ENABLED and debug` are both True.

---

## Differences from Pico App

| Feature | Pico (`app/`) | SDK (`tools/client_sdk_hardware/`) |
|---------|---------------|------------------------------------|
| **Platform** | MicroPython (RP2350) | CPython 3.x |
| **HTTP client** | `urequests` | `requests` |
| **JSON** | `ujson` | `json` |
| **Response close** | **Required** (`r.close()` in finally) | Optional (auto-pooled) |
| **WiFi** | `network.WLAN()` + auto-connect splash | Assumes network already up |
| **Display** | PicoGraphics (PEN_P4, 240×135 LCD) | None (stdout logging only) |
| **Menu UI** | Full menu system (weather, status, API toggles) | None (extend `main.py` loop) |
| **Heartbeat GW** | Lazy (created on first WiFi+tick) | Created at boot (passed to constructor) |
| **Kill detection** | Shows KILLED screen, keeps ticking | Logs state, keeps ticking |
| **Remote config** | Synced every loop for some keys (debug) | Fetched every heartbeat, used via `hb.config` |

---

## Example Use Cases

### Raspberry Pi Temperature Monitor

```python
import subprocess
import time

from boot import boot, _log, load_settings, save_settings
from heartbeat import Heartbeat

def get_temp():
    result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
    return float(result.stdout.replace('temp=', '').replace("'C\n", ''))

def main():
    gw = boot()
    if gw is None:
        return

    _settings = load_settings()
    hb = Heartbeat(gw, status=lambda: f"temp={get_temp():.1f}C",
                   save=save_settings, dbg=_log)
    hb.config = _settings.get("hw_config")

    while True:
        hb.tick()
        temp = get_temp()
        if temp > 80:
            hb.health = "error"
            _log(f"[error] Critical temp: {temp}°C")
        elif temp > 70:
            hb.health = "warning"
            _log(f"[warn] High temp: {temp}°C")
        else:
            hb.health = "ok"

        time.sleep(5)

if __name__ == "__main__":
    main()
```

### Docker Container Health Check

```python
import subprocess
import time

from boot import boot, _log, load_settings, save_settings
from heartbeat import Heartbeat
from config import HB_INTERVAL

def check_containers():
    result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'],
                          capture_output=True, text=True)
    return result.stdout.strip().split('\n')

def main():
    gw = boot()
    if gw is None:
        return

    _settings = load_settings()
    hb = Heartbeat(gw, status=lambda: f"{len(check_containers())} containers",
                   save=save_settings, dbg=_log)
    hb.config = _settings.get("hw_config")

    while True:
        hb.tick()
        containers = check_containers()
        _log(f"[docker] {containers}")

        time.sleep(HB_INTERVAL)

if __name__ == "__main__":
    main()
```

---

## Troubleshooting

### Network Unreachable

**Symptom:** `[boot] Timeout after 10s — no network`

**Fixes:**
1. Check gateway URL in `config.py`
2. Verify network connectivity: `curl https://api.novaroma-homelab.uk/health`
3. Check firewall (allow HTTPS outbound on port 443)
4. Increase `BOOT_TIMEOUT` in `config.py`

### Auth Failed

**Symptom:** `[boot] Auth failed: 401 Client Error: Unauthorized`

**Fixes:**
1. Check username/password in `config.py`
2. Verify user exists and `is_active: true` on gateway
3. Check gateway logs for auth errors

### Heartbeat Errors

**Symptom:** `[HB] error: <error>`

**Common causes:**
- Gateway timeout → network issue, retry on next tick
- Token expired → should auto-refresh, check for `401` in error
- Gateway down → check gateway status
- Device not registered → register via `/settings/hardware` first

**Note:** Heartbeat errors are logged but do not stop the heartbeat loop. The device continues reporting.

---

## License

MIT — see LICENSE file in project root

Built with 💙 by JestingDart4369
