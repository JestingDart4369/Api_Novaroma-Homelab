# ──────────────────────────────────────────────────────────────
# API Gateway – client configuration
# ──────────────────────────────────────────────────────────────
# Copy this file to  config.py  and fill in your values.
# NEVER commit config.py to Git — add it to .gitignore.
# ──────────────────────────────────────────────────────────────

# Gateway URL (public endpoint)
GATEWAY_URL = "https://your-gateway-url.com"

# Your gateway account credentials  (created via /settings/users)
GATEWAY_USERNAME = "your-username"
GATEWAY_PASSWORD = "your-password"

# ── heartbeat registration names ────────────────────────────
# Each name must be registered on the gateway FIRST:
#   POST /settings/software   {"name": "..."}   ← for software
#   POST /settings/hardware   {"name": "..."}   ← for hardware
# Only fill in what you're using.

SOFTWARE_NAME = "my-app"         # ← change or remove
# HARDWARE_NAME = "my-device"    # ← uncomment if using hardware
