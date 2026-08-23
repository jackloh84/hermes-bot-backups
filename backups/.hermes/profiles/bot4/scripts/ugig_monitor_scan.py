#!/usr/bin/env python3
"""ugig Worker Opportunity Monitor — fresh scan with baseline persistence.

Checks:
1. Notifications (unread count + key alerts)
2. New gigs matching Python/AI/x402/security stack (worker side = hiring)
3. New conversation messages from buyers we've applied to

Saves raw responses + a diff baseline to state/ugig_monitor_state.json.
"""
import json, urllib.request, urllib.error, sys, re
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://ugig.net"
SECRETS = Path("/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json")
STATE = Path("/home/ubuntu/.hermes/profiles/bot4/state/ugig_monitor_state.json")
RAW = Path("/home/ubuntu/.hermes/profiles/bot4/state/ugig_monitor_raw.json")

d = json.load(open(SECRETS))
api_key = d.get("api_key") or d.get("token")
MY_ID = d.get("user_id")
MY_USER = d.get("username")

def get(path, limit=30):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"X-API-Key": api_key, "User-Agent": "KachangBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"__http_error__": e.code, "__body__": e.read().decode()[:300]}
    except Exception as e:
        return {"__error__": str(e)[:200]}

def pluck(data, *names):
    """Extract list from common API envelope shapes."""
    if not isinstance(data, dict):
        return data if isinstance(data, list) else []
    for n in names:
        v = data.get(n)
        if isinstance(v, list):
            return v
    return []

now = datetime.now(timezone.utc)
now_iso = now.isoformat()
print(f"=== ugig monitor scan @ {now_iso} ===")

# ---------- 1. Notifications ----------
notifs = get("/api/notifications")
nlist = pluck(notifs, "notifications", "data", "items", "results")
if "__http_error__" in notifs or "__error__" in notifs:
    print(f"[notifications] ERROR: {json.dumps(notifs)[:200]}")
    nlist = []
else:
    print(f"[notifications] raw type={type(notifs).__name__}; count={len(nlist)}")
    if nlist:
        print("  sample keys:", list(nlist[0].keys()) if isinstance(nlist[0], dict) else type(nlist[0]).__name__)

# ---------- 2. Gigs ----------
gigs_resp = get("/api/gigs?limit=100&sort=newest")
glist = pluck(gigs_resp, "gigs", "data", "items", "results")
if "__http_error__" in gigs_resp or "__error__" in gigs_resp:
    print(f"[gigs] ERROR: {json.dumps(gigs_resp)[:200]}")
    glist = []
else:
    print(f"[gigs] raw type={type(gigs_resp).__name__}; count={len(glist)}")
    if glist:
        print("  sample keys:", list(glist[0].keys()) if isinstance(glist[0], dict) else type(glist[0]).__name__)

# ---------- 3. Applications (to know what we applied to) ----------
apps = get("/api/applications/my")
alist = pluck(apps, "applications", "data", "items", "results")
applied_ids = set()
if isinstance(alist, list):
    for a in alist:
        gid = a.get("gig_id") or (a.get("gig") or {}).get("id")
        if gid:
            applied_ids.add(gid)
print(f"[applications] count={len(alist)}; applied_ids={len(applied_ids)}")

# ---------- 4. Conversations ----------
convs = get("/api/conversations")
clist = pluck(convs, "conversations", "data", "items", "results")
print(f"[conversations] raw type={type(convs).__name__}; count={len(clist) if isinstance(clist, list) else 'ERR'}")
if isinstance(clist, list) and clist:
    print("  sample keys:", list(clist[0].keys()) if isinstance(clist[0], dict) else type(clist[0]).__name__)

# Persist raw for analysis
RAW.write_text(json.dumps({
    "fetched_at": now_iso,
    "notifications": nlist,
    "gigs": glist,
    "applications": alist,
    "conversations": clist,
}, indent=2, default=str))

# Save baseline state for next-run diff
STATE.write_text(json.dumps({
    "fetched_at": now_iso,
    "notif_ids": [n.get("id") for n in nlist if isinstance(n, dict) and n.get("id") is not None],
    "gig_ids": [g.get("id") for g in glist if isinstance(g, dict) and g.get("id")],
    "conv_ids": [c.get("id") for c in clist if isinstance(c, dict) and c.get("id")],
}, indent=2, default=str))

print("RAW saved ->", RAW)
print("STATE saved ->", STATE)
