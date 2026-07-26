#!/usr/bin/env python3
"""
self-rescue.py — Each bot's own self-rescue cron.

Every 15 min, this runs inside the bot's own profile (via cron) and checks
ONLY its own gateway. If something's wrong with itself, it tries the same
conservative fixes as bot-rescue.py. If it can't fix, it creates a Kanban
task for DevOps Bot (bot6) to investigate.

Why this is separate from bot-rescue.py:
  - bot-rescue.py runs every 5m from bot6 → monitors the whole fleet
  - self-rescue.py runs every 15m from each bot → catches self-issues even if
    DevOps bot itself is down (defense in depth)
  - If a bot can't self-fix, it files Kanban so another bot (DevOps) can help

Used as a cron script per-profile:
  schedule='every 15m'
  script='self-rescue.py'
  no_agent=True

Self-rescue.py silently does its work — only outputs on failure.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERMES_ROOT = Path("/home/ubuntu/.hermes")
KANBAN_DB = HERMES_ROOT / "kanban.db"

# Detect current profile from HERMES_HOME (set by systemd service)
# Falls back to parsing cmdline for safety
def detect_current_profile() -> str | None:
    # 1. Try HERMES_HOME env
    home = os.environ.get("HERMES_HOME", "")
    if home:
        home_path = Path(home).resolve()
        if home_path.parent.name == "profiles":
            return home_path.name
    # 2. Fallback: parse our own cmdline
    try:
        with open("/proc/self/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", errors="ignore")
        for token in cmdline.split("\x00"):
            if token.startswith("--profile="):
                return token.split("=", 1)[1]
    except OSError:
        pass
    return None


# Conservative self-fixes (subset of bot-rescue.py — only the ones a bot
# can safely do to itself without coordination)

def check_service_active(service_name: str) -> bool:
    try:
        r = subprocess.run(
            ["/usr/bin/systemctl", "--user", "is-active", f"{service_name}.service"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() == "active"
    except (subprocess.TimeoutExpired, OSError):
        return False


def check_gateway_state(profile: str) -> tuple[bool, str]:
    state_file = HERMES_ROOT / "profiles" / profile / "gateway_state.json"
    if not state_file.exists():
        return False, "no_state_file"
    try:
        with open(state_file) as f:
            s = json.load(f)
        gw = s.get("gateway_state", "unknown")
        tg = s.get("platforms", {}).get("telegram", {}).get("state", "unknown")
        return (gw == "running" and tg == "connected"), f"gw={gw},tg={tg}"
    except (OSError, json.JSONDecodeError):
        return False, "corrupt_state"


def restart_self_service(profile: str) -> tuple[bool, str]:
    svc = f"hermes-gateway-{profile}"
    try:
        r = subprocess.run(
            ["/usr/bin/systemctl", "--user", "restart", f"{svc}.service"],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0, r.stderr.strip() or "restarted"
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)


def file_kanban_task(profile: str, issue: str) -> bool:
    """Create a Kanban task asking DevOps (bot6) to investigate this bot."""
    if not KANBAN_DB.exists():
        return False
    # Use hermes CLI to create the task — the bot's own credentials work for kanban
    title = f"[{profile}] Self-rescue FAILED: {issue[:80]}"
    body = (
        f"Bot {profile} tried self-rescue at {time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"but could not recover. Issue: {issue}.\n\n"
        f"Requested action: please investigate and either fix manually or escalate to Jack."
    )
    try:
        # kanban create takes positional title + --body flag
        r = subprocess.run(
            ["/home/ubuntu/.local/bin/hermes", "kanban", "create",
             "--assignee", "bot6",
             "--priority", "high",
             "--body", body,
             title],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode == 0:
            return True
        # Debug for silent failures
        sys.stderr.write(f"kanban create failed: rc={r.returncode} stderr={r.stderr[:200]}\n")
        return False
    except (subprocess.TimeoutExpired, OSError) as e:
        sys.stderr.write(f"kanban create exception: {e}\n")
        return False


def main() -> int:
    profile = detect_current_profile()
    if not profile:
        print("⚠ self-rescue: cannot detect current profile (HERMES_HOME unset)")
        return 0  # silent — not our job to fix profile detection

    # Don't self-rescue the DevOps bot itself (it would conflict with bot-rescue.py)
    # and don't rescue MC (it has its own logic)
    if profile in ("bot6", "master-control"):
        return 0

    svc_active = check_service_active(f"hermes-gateway-{profile}")
    tg_ok, tg_detail = check_gateway_state(profile)

    if svc_active and tg_ok:
        return 0  # all good — silent

    # Try to self-fix: restart our own service
    issue = f"service_active={svc_active}, telegram={tg_detail}"
    ok, msg = restart_self_service(profile)
    if not ok:
        # Couldn't even restart — file Kanban for DevOps
        if file_kanban_task(profile, issue):
            print(f"⚠ {profile}: self-rescue failed ({msg}); Kanban task filed for DevOps")
        else:
            print(f"🚨 {profile}: self-rescue failed AND couldn't file Kanban. Issue: {issue}")
        return 1

    # Restart succeeded — wait for Telegram reconnect then re-verify
    # (Telegram polling handshake can take 10-15s on cold start)
    time.sleep(15)
    tg_ok_after, tg_detail_after = check_gateway_state(profile)
    if tg_ok_after:
        return 0  # Fixed silently — no output

    # Still broken after restart
    issue_after = f"service restarted but telegram still {tg_detail_after}"
    if file_kanban_task(profile, issue_after):
        print(f"⚠ {profile}: restarted but Telegram still down; Kanban task filed for DevOps")
    else:
        print(f"🚨 {profile}: restarted but Telegram still {tg_detail_after}; couldn't file Kanban")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"⚠ self-rescue crashed: {type(e).__name__}: {e}")
        sys.exit(0)  # silent on crash — don't spam Jack