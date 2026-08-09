#!/usr/bin/env python3
"""Merchant Center approval watchdog — silent unless state changes.

Prints ONLY when: all 4 products reach approved/active, OR the issue set
changes vs the last run (state file). Empty stdout = silent (cron no_agent
delivers nothing). State persisted in mc_approval_state.json.
"""
import json
import os
import urllib.request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mc_approval_state.json")
MC = "5834604707"
BASE = f"https://content.googleapis.com/content/v2.1/{MC}"
OIDS = ["tiktok-hooks", "content-creator-pack", "business-automation", "solopreneur-launchpad"]

data = json.load(open("/home/ubuntu/.hermes/google-ads/token.json"))
creds = Credentials(
    token=None, refresh_token=data["refresh_token"], token_uri=data["token_uri"],
    client_id=data["client_id"], client_secret=data["client_secret"], scopes=data["scopes"],
)
creds.refresh(Request())


def call(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {creds.token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def main():
    snapshot = {}
    for oid in OIDS:
        st, status = call(f"/productstatuses/online:en:SG:{oid}")
        if st != 200:
            snapshot[oid] = {"status": f"HTTP {st}"}
            continue
        dests = {d.get("destination"): d.get("status") for d in status.get("destinationStatuses", [])}
        issues = sorted({i.get("code") for i in status.get("itemLevelIssues", [])})
        snapshot[oid] = {"dests": dests, "issues": issues}

    # compute headline state
    states = [s.get("dests", {}).get("Shopping", s.get("status", "?")) for s in snapshot.values()]
    all_approved = all(st in ("approved", "active") for st in states)
    any_disapproved = any(st == "disapproved" for st in states)
    all_pending = all(st in ("pending", "under_review", "participation_disapproved", "active") for st in states)

    try:
        prev = json.load(open(STATE))
    except Exception:
        prev = None

    lines = []
    if all_approved and prev != "approved":
        lines.append("🎉 Merchant Center: ALL 4 Kachang-Sia products APPROVED!")
        for oid in OIDS:
            lines.append(f"  • {oid} — Shopping: approved")
        lines.append("Free listings live on Google Shopping. Next: consider campaigns (needs Jack's budget OK).")
        json.dump("approved", open(STATE, "w"))
    elif prev == "approved":
        return  # already reported approval; stay silent
    elif any_disapproved:
        # report only on change from previous run
        cur = json.dumps(snapshot, sort_keys=True)
        if prev != cur:
            lines.append("⚠️ Merchant Center: a product has an issue.")
            for oid, s in snapshot.items():
                dst = s.get("dests", {})
                if dst.get("Shopping") == "disapproved" or dst.get("SurfacesAcrossGoogle") == "disapproved":
                    lines.append(f"  • {oid}: {dst} issues={s.get('issues')}")
            json.dump(snapshot, open(STATE, "w"))
    elif all_pending and prev is None:
        lines.append("📋 Merchant Center: 4 products still in initial review (normal for new accounts). Will ping when approved.")
        json.dump(snapshot, open(STATE, "w"))
    elif all_pending:
        # still pending, no change -> silent
        pass
    else:
        cur = json.dumps(snapshot, sort_keys=True)
        if prev != cur:
            lines.append("📋 Merchant Center status changed:")
            for oid, s in snapshot.items():
                lines.append(f"  • {oid}: {s.get('dests', s.get('status'))} issues={s.get('issues')}")
            json.dump(snapshot, open(STATE, "w"))

    if lines:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
