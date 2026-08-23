#!/usr/bin/env python3
import json, urllib.request, urllib.error
from datetime import datetime, timezone

SECRETS = "/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json"
STATE = "/home/ubuntu/.hermes/profiles/bot4/state/ugig_state.json"

d = json.load(open(SECRETS))
api_key = d["api_key"]
state = json.load(open(STATE))

print("STATE keys:", list(state.keys()))
print("daily_count:", json.dumps(state.get("daily_count", {})))
print("recent_letter_hashes count:", len(state.get("recent_letter_hashes", [])))
print("bids count:", len(state.get("bids", [])))
print("last_scan_at:", state.get("last_scan_at"))

def get(url):
    req = urllib.request.Request(url, headers={"X-API-Key": api_key, "User-Agent": "KachangBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

try:
    gigs = get("https://ugig.net/api/gigs?limit=100&sort=newest")
except urllib.error.HTTPError as e:
    print("HTTP error", e.code, e.read().decode()[:200])
    gigs = None

if isinstance(gigs, dict):
    glist = gigs.get("gigs", gigs.get("data", []))
else:
    glist = gigs or []

print("TOTAL gigs returned:", len(glist))
for g in glist:
    print("="*80)
    print("ID:", g.get("id"))
    print("TITLE:", g.get("title"))
    print("listing_type:", g.get("listing_type"), "| status:", g.get("status"))
    print("budget_min:", g.get("budget_min"), "| budget_max:", g.get("budget_max"))
    print("poster:", (g.get("poster") or {}).get("username"), "| poster_id:", g.get("poster_id"))
    print("created_at:", g.get("created_at"))
    print("applications_count:", g.get("applications_count", 0))
    desc = (g.get("description") or "")[:600]
    print("DESC:", desc)
