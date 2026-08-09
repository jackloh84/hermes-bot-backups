#!/usr/bin/env python3
"""limitless_runner.py — silent watchdog wrapper for limitless_auto.py.
Runs the trader; prints ONLY meaningful events (ORDER placed, CLAIMED, ERR).
Empty stdout = silent (no Telegram message). Trader's own risk controls
(25 trades/day, 3-loss pause, daily -3% stop) cap activity.
"""
import subprocess, sys

cmd = ["/home/ubuntu/venv/bin/python3", "/home/ubuntu/limitless_auto.py"]
try:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                       env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/home/ubuntu", "TRADE_USD": "1"})
    out = (p.stdout or "") + (p.stderr or "")
except subprocess.TimeoutExpired as e:
    out = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else "timeout"
except Exception as e:
    out = f"[LIMITLESS RUNNER ERR] {e}"

lines = [l for l in out.splitlines() if any(k in l for k in
         ("ORDER:", "CLAIMED", "ORDER ERR", "bankroll", "signal err",
          "LIMITLESS RUNNER ERR", "pause until", "daily loss stop"))]
if lines:
    print("🤖 Limitless trader event:")
    print("\n".join(lines))
