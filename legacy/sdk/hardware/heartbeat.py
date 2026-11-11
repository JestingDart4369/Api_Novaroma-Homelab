# ──────────────────────────────────────────────────────────────
# heartbeat.py  –  cooperative heartbeat + config fetch
# ──────────────────────────────────────────────────────────────
# Three-tier control system:
# 1. server_enabled (503) - Hard API block, nothing gets through
# 2. is_active (response) - Device-side block, device stops itself
# 3. health property - Device self-reports status
#
# Usage:
#   from heartbeat import Heartbeat
#   hb = Heartbeat(gw, status=lambda: "running",
#                  save=save_settings, dbg=_log)
#   while True:
#       hb.tick()
#       # Update hb.health based on conditions
#       if critical: hb.health = "killed"
#       time.sleep(1)
# ──────────────────────────────────────────────────────────────

import time

from config import HARDWARE_NAME, HB_INTERVAL


class Heartbeat:
    """Cooperative heartbeat manager with three-tier control support.

    gw     – a GatewayClient returned by boot().
    status – callable returning the current status string.
    save   – callable(dict) to persist state (merged into settings.json).
    dbg    – callable(str) for logging.
    """

    def __init__(self, gw, status=None, save=None, dbg=None):
        self.gw      = gw
        self.status  = status or (lambda: "idle")
        self._save   = save   or (lambda d: None)
        self._dbg    = dbg    or (lambda m: None)

        # Three-tier control
        self.health  = "ok"        # health: ok, warning, error, killed (self-report)
        self.is_active = True      # is_active from server (device-side block signal)
        self.state   = "waiting"   # waiting | ok | warn | killed (device state)

        self.config  = None        # last-known remote config
        self._next   = 0           # time.time() trigger
        self.last_ping_ms = None   # gateway response time
        self._log_event = None     # optional external logger

    # ── public ──────────────────────────────────────────────────

    def force(self):
        """Fire heartbeat on the next tick."""
        self._next = 0

    def tick(self):
        """Call every loop iteration.  Fires heartbeat when the interval expires."""
        if time.time() < self._next:
            return
        self._next = time.time() + HB_INTERVAL
        self._heartbeat()

    # ── internal ────────────────────────────────────────────────

    def _heartbeat(self):
        t0 = time.time()
        old_state = self.state

        try:
            response = self.gw.push_hardware_heartbeat(
                HARDWARE_NAME,
                health=self.health,
                details={"uptime": t0, "status": self.status()},
            )
            self.last_ping_ms = int((time.time() - t0) * 1000)

            # Check device-side block signal (is_active)
            if isinstance(response, dict):
                self.is_active = response.get("is_active", True)
                if not self.is_active and self.state != "killed":
                    self.state = "killed"
                    self._save({"hb_killed": True})
                    self._dbg(f"[HB] KILLED (is_active=false)")
                    if old_state != self.state and self._log_event:
                        self._log_event("hb", f"{old_state} -> killed (is_active)")
                    return

            # success upgrades warn/waiting → ok
            if self.state != "killed":
                self.state = "ok"

            # log state change
            if old_state != self.state and self._log_event:
                self._log_event("hb", f"{old_state} -> {self.state}")

            self._dbg(f"[HB] {self.health} ({self.last_ping_ms}ms)")

        except Exception as e:
            self.last_ping_ms = None
            code = getattr(getattr(e, "response", None), "status_code", 0)

            if code == 503:
                # server_enabled=false - Hard API block
                self.state = "killed"
                self._save({"hb_killed": True})
                self._dbg(f"[HB] BLOCKED (503) - server_enabled=false")

                if old_state != self.state and self._log_event:
                    self._log_event("hb", f"{old_state} -> killed (503)")
            else:
                # All other errors are warnings
                self.state = "warn"
                self._dbg(f"[HB] warn: {e}")

                if old_state != self.state and self._log_event:
                    self._log_event("hb", f"{old_state} -> warn")

        # fetch config
        self._fetch_config()

    def _fetch_config(self):
        try:
            new_config, _ = self.gw.get_hardware_config(HARDWARE_NAME)

            if new_config != self.config:
                self.config = new_config
                self._save({"hw_config": new_config})
                self._dbg(f"[HB] config: {new_config}")
        except Exception as e:
            self._dbg(f"[HB] config err: {e}")
