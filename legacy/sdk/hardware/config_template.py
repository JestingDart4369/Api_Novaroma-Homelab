# ──────────────────────────────────────────────────────────────
# config.py  –  boot essentials (WiFi + heartbeat only)
# ──────────────────────────────────────────────────────────────
# This file holds the bare minimum needed to start up and reach
# the gateway.  Everything else (display settings, URLs, labels …)
# is fetched via get_hardware_config() and persisted in
# settings.json — exactly the same pattern as the Pico killswitch.
#
# Copy this file to config.py and fill in your credentials.
# NEVER commit config.py to Git if you fill in real credentials.
# ──────────────────────────────────────────────────────────────

# ── gateway ─────────────────────────────────────────────────────
GATEWAY_URL      = "https://your-gateway-url.com"
GATEWAY_USERNAME = ""          # fill in your username
GATEWAY_PASSWORD = ""          # fill in your password
HARDWARE_NAME    = ""          # registered device name on the gateway

# ── WiFi ────────────────────────────────────────────────────────
# Only used on bare-metal (Pico etc).  Desktop / server ignores this.
WIFI_NETWORKS = [
    # ("SSID", "password"),
]

# ── timings ─────────────────────────────────────────────────────
BOOT_TIMEOUT  = 10      # seconds: max wait for network at boot
HB_INTERVAL   = 30      # seconds between heartbeats

# ── display ─────────────────────────────────────────────────────
# Set False for headless hardware (no screen, no stdout progress).
# Every log / draw call in boot.py and main.py checks this flag
# before doing anything.
DISPLAY_ENABLED = True
