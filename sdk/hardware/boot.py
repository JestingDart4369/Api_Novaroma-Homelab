# ──────────────────────────────────────────────────────────────
# boot.py  –  settings, logging, network check + gateway auth
# ──────────────────────────────────────────────────────────────
# CPython mirror of the Pico boot sequence: poll until the gateway
# host is reachable, then authenticate and return a warm
# GatewayClient.
#
# Logging:  set {"debug": true} in settings.json to enable stdout
# output.  DISPLAY_ENABLED in config.py is the master switch for
# headless hardware (overrides settings.json).
#
# Usage:
#   from boot import boot, _log, load_settings, save_settings
#   gw = boot()           # GatewayClient or None
# ──────────────────────────────────────────────────────────────

import time
import socket
import json

from gateway import GatewayClient
from config import (
    GATEWAY_URL,
    GATEWAY_USERNAME,
    GATEWAY_PASSWORD,
    HARDWARE_NAME,
    BOOT_TIMEOUT,
    DISPLAY_ENABLED,
)


# ── settings persistence ────────────────────────────────────────
_SETTINGS_FILE = "settings.json"


def load_settings():
    try:
        with open(_SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(updates):
    """Merge *updates* into settings.json — preserves other keys."""
    try:
        s = load_settings()
        for k in updates:
            s[k] = updates[k]
        with open(_SETTINGS_FILE, "w") as f:
            json.dump(s, f)
    except Exception:
        pass


# ── logging ─────────────────────────────────────────────────────
_settings = load_settings()
_debug    = _settings.get("debug", False)


def _log(msg):
    """Print when DISPLAY_ENABLED is set AND debug is on in settings.json."""
    if DISPLAY_ENABLED and _debug:
        print(msg)


# ── internal ────────────────────────────────────────────────────

def _host_reachable(url, timeout=3):
    """TCP probe — True if the gateway host accepts a connection."""
    try:
        host = url.split("://", 1)[1].rstrip("/").split("/")[0]
        port = 443 if url.startswith("https") else 80
        if ":" in host:
            host, port = host.rsplit(":", 1)
            port = int(port)
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


# ── public ──────────────────────────────────────────────────────

def boot():
    """Run the full boot sequence.

    1. Verify HARDWARE_NAME is set.
    2. Poll until the gateway host is reachable (or BOOT_TIMEOUT).
    3. Authenticate and return a warmed-up GatewayClient.

    Returns GatewayClient on success, None on any failure.
    """
    _log("[boot] Starting")

    if not HARDWARE_NAME:
        _log("[boot] HARDWARE_NAME is empty — set it in config.py")
        return None

    # ── wait for network ────────────────────────────────────────
    _log("[boot] Checking network")
    t0 = time.time()
    while True:
        if _host_reachable(GATEWAY_URL):
            _log("[boot] Network OK")
            break
        elapsed = time.time() - t0
        if elapsed >= BOOT_TIMEOUT:
            _log(f"[boot] Timeout after {BOOT_TIMEOUT}s — no network")
            return None
        time.sleep(0.5)

    # ── authenticate ────────────────────────────────────────────
    try:
        gw = GatewayClient(GATEWAY_URL, GATEWAY_USERNAME, GATEWAY_PASSWORD)
        gw._get_token()          # trigger first login right away
        _log("[boot] Authenticated")
        return gw
    except Exception as e:
        _log(f"[boot] Auth failed: {e}")
        return None
