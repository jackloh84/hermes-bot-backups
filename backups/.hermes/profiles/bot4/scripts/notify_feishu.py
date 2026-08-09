#!/usr/bin/env python3
"""notify_feishu.py — shared Feishu alert helper for trading bots.

Usage:
  python3 notify_feishu.py "message text"

Sends the message to Jack's Feishu Home channel via `hermes send`.
Used by gains_intraday.py and limitless_auto.py on real trade events
(open/close/claim/stop) so Jack sees every bet with full details.

Silent on failure — trading must never block on a notification.
"""
import subprocess, sys, shlex

FEISHU = "feishu"

def notify(text: str) -> bool:
    try:
        cmd = ["hermes", "send", "--to", FEISHU, text]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False

if __name__ == "__main__":
    msg = " ".join(sys.argv[1:])
    if not msg:
        sys.exit(0)
    ok = notify(msg)
    sys.exit(0 if ok else 1)
