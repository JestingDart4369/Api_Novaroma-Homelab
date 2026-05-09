"""
Heartbeat – background thread that pushes health to the API Gateway.

Three-tier control system:
1. server_enabled (503) - Hard API block, nothing gets through
2. is_active (response field) - Device-side block, device stops itself
3. health (self-report) - Device reports own status

Usage:
    from gateway   import GatewayClient
    from heartbeat import Heartbeat

    gw = GatewayClient("https://api.novaroma-homelab.uk", "user", "pass")

    # --- software ---
    hb = Heartbeat(gw, kind="software", name="my-app")
    hb.start()                                          # first beat + background loop
    hb.set_health("warning", {"disk": "full"})          # update anytime
    hb.set_health("killed", {"reason": "shutting down"})  # self-report

    # --- hardware ---
    hb = Heartbeat(gw, kind="hardware", name="router-hall")
    hb.start()
    hb.set_health("error", {"cpu_temp_c": 95})
"""

import os
import sys
import threading
from typing import Optional, Dict

import requests

from gateway import GatewayClient

HEARTBEAT_INTERVAL = 30  # seconds


class Heartbeat:
    def __init__(self, client: GatewayClient, *, kind: str, name: str):
        """
        client  – an authenticated GatewayClient instance
        kind    – "software"  or  "hardware"
        name    – the name registered on the gateway (must already exist
                  in /settings/software  or  /settings/hardware)
        """
        if kind not in ("software", "hardware"):
            raise ValueError('kind must be "software" or "hardware"')

        self._client = client
        self._kind = kind
        self._name = name

        # current health — updated via set_health(), read on every beat
        self._health: str = "ok"
        self._details: Optional[Dict] = {"status": "running"}

        self._stop = threading.Event()
        self.killed = threading.Event()   # set when is_active=false (device-side kill)
        self.server_blocked = threading.Event()  # set when server_enabled=false (503)

    # ── public helpers ──────────────────────────────────────────────

    def set_health(self, health: str, details: Optional[Dict] = None):
        """Update health from anywhere in your code.  Picked up on next beat."""
        if health not in ("ok", "warning", "error", "killed"):
            raise ValueError('health must be "ok", "warning", "error", or "killed"')
        self._health = health
        if details is not None:
            self._details = details

    # ── single beat ─────────────────────────────────────────────────

    def _beat(self) -> bool:
        """POST one heartbeat.  Returns False on server_enabled=false (503) or is_active=false."""
        try:
            if self._kind == "software":
                response = self._client.push_software_heartbeat(self._name, self._health, self._details)
            else:
                response = self._client.push_hardware_heartbeat(self._name, self._health, details=self._details)

            # Check device-side kill (is_active)
            if isinstance(response, dict) and not response.get("is_active", True):
                print(f"[HEARTBEAT] is_active=false - device-side kill triggered", flush=True)
                return False  # Device blocks itself

            return True

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 503:
                # server_enabled=false - Hard API block
                self.server_blocked.set()
                return False
            print(f"[HEARTBEAT] warning: {e}", flush=True)
            return True

        except requests.exceptions.RequestException as e:
            # network problems → warn but keep running
            print(f"[HEARTBEAT] network warning: {e}", flush=True)
            return True

    # ── background loop ─────────────────────────────────────────────

    def _loop(self):
        while not self._stop.wait(HEARTBEAT_INTERVAL):
            if not self._beat():
                self.killed.set()
                if self.server_blocked.is_set():
                    print(
                        f"\n[HEARTBEAT] '{self._name}' blocked server-side"
                        " (server_enabled=false) — shutting down\n",
                        flush=True,
                    )
                else:
                    print(
                        f"\n[HEARTBEAT] '{self._name}' killed device-side"
                        " (is_active=false) — shutting down\n",
                        flush=True,
                    )
                self._stop.wait(1)   # 1 s grace period
                os._exit(1)

    # ── lifecycle ───────────────────────────────────────────────────

    def start(self):
        """Run the first beat immediately, then start the background thread.

        Calls sys.exit(1) right away if blocked."""
        if not self._beat():
            if self.server_blocked.is_set():
                print(
                    f"[HEARTBEAT] '{self._name}' blocked server-side"
                    " (server_enabled=false). Exiting.",
                    flush=True,
                )
            else:
                print(
                    f"[HEARTBEAT] '{self._name}' killed device-side"
                    " (is_active=false). Exiting.",
                    flush=True,
                )
            sys.exit(1)

        self._stop.clear()
        self.killed.clear()
        self.server_blocked.clear()
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[HEARTBEAT] Started — reporting as {self._kind} '{self._name}'", flush=True)

    def stop(self):
        """Signal the background thread to stop."""
        self._stop.set()
