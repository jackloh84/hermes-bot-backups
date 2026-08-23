#!/usr/bin/env python3
import json, urllib.request, urllib.error
from datetime import datetime, timezone

SECRETS = "/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json"
d = json.load(open(SECRETS))
api_key = d["api_key"]

def get(url):
    req = urllib.request.Request(url, headers={"X-API-Key": api_key, "User-Agent": "KachangBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# my applications
try:
    apps = get("https://ugig.net/api/applications/my")
except urllib.error.HTTPError as e:
    print("apps HTTP", e.code, e.read().decode()[:300])
    apps = None

if isinstance(apps, dict):
    alist = apps.get("applications", apps.get("data", []))
else:
    alist = apps or []

applied_ids = set()
for a in alist:
    gid = a.get("gig_id") or a.get("gig", {}).get("id")
    if gid:
        applied_ids.add(gid)
print("TOTAL applications:", len(alist))
print("applied gig_ids (first 60):")
for gid in sorted(applied_ids)[:60]:
    print("  ", gid)

# my profile id
try:
    prof = get("https://ugig.net/api/profile")
    my_id = prof.get("id") or (prof.get("user") or {}).get("id")
    print("my user id:", my_id)
except Exception as e:
    my_id = None
    print("profile err", str(e)[:120])
