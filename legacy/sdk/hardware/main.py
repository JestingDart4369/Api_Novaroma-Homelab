#!/usr/bin/env python3
# ──────────────────────────────────────────────────────────────
# main.py  –  minimal hardware-client loop
# ──────────────────────────────────────────────────────────────
# 1. Fill in config.py  (gateway creds + HARDWARE_NAME at minimum).
# 2. Run:  python main.py
# 3. Extend the loop body or change hb.health for your hardware.
#    All remote settings come from get_hardware_config() — nothing
#    extra needed in config.py.
# ──────────────────────────────────────────────────────────────

import time

from config    import HB_INTERVAL
from boot      import boot, _log, load_settings, save_settings
from heartbeat import Heartbeat


def main():
    gw = boot()
    if gw is None:
        _log("[main] Boot failed — check config.py and network")
        return

    # ── heartbeat — load persisted config ──────────────────────
    _settings = load_settings()
    hb = Heartbeat(gw, status=lambda: "running",
                   save=save_settings, dbg=_log)
    hb.config = _settings.get("hw_config")
    _log(f"[main] Heartbeat active, interval {HB_INTERVAL}s  …  Ctrl-C to stop")

    while True:
        hb.tick()

        # ── add your own logic here ────────────────────────────
        # Read sensors, check conditions, update health:
        # if critical_error:
        #     hb.health = "killed"
        # elif warning_condition:
        #     hb.health = "warning"
        # else:
        #     hb.health = "ok"

        time.sleep(1)  # tick loop; actual HB fires every HB_INTERVAL


if __name__ == "__main__":
    main()
