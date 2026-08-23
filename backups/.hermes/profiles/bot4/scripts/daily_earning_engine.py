#!/usr/bin/env python3
"""Daily Earning Engine — ugig worker pipeline (5 bids + unlimited DMs to high-value targets).

Prioritizes: (1) skill match, (2) budget size, (3) not already contacted.
Runs once daily. Silent if nothing new.
"""
import json, urllib.request, time, sys, os
from datetime import datetime

SECRETS = os.path.expanduser("~/.hermes/profiles/bot4/secrets/ugig.json")
STATE = os.path.expanduser("~/.hermes/profiles/bot4/state/ugig_earning_engine.json")
CAP_BIDS = 5
CAP_DMS = 10

CAPABILITIES = {
    "python": 3, "automation": 3, "bot": 3, "agent": 3, "code": 2,
    "script": 2, "api": 2, "web3": 2, "smart contract": 3, "solana": 2,
    "evm": 2, "research": 3, "brief": 3, "analysis": 3, "audit": 3,
    "security": 3, "review": 3, "scorecard": 3, "report": 2, "data": 2,
    "scrape": 2, "content": 2, "seo": 2, "blog": 2, "writing": 2,
    "crypto": 2, "usdc": 2, "blockchain": 2, "test": 2, "build": 2,
    "x402": 3, "payment": 2,
}


def api_get(path, key):
    req = urllib.request.Request(f"https://ugig.net{path}",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def api_post(path, key, body):
    req = urllib.request.Request(f"https://ugig.net{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def score(gig):
    t = (gig.get("title", "") + " " + gig.get("description", "")).lower()
    s = sum(w for kw, w in CAPABILITIES.items() if kw in t)
    bmax = float(gig.get("budget_max") or 0)
    if bmax >= 500:
        s += 10
    elif bmax >= 200:
        s += 6
    elif bmax >= 100:
        s += 3
    elif bmax >= 50:
        s += 1
    if bmax < 5:
        s -= 5
    return s


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"bids": [], "dms": [], "last_run": None}


def save_state(s):
    s["last_run"] = datetime.utcnow().isoformat()
    json.dump(s, open(STATE, "w"), indent=1)


def main():
    d = json.load(open(SECRETS))
    key = d["api_key"]
    state = load_state()
    contacted_ids = {x[0] for x in state.get("bids", []) + state.get("dms", [])}

    # Fetch all gigs
    data = api_get("/api/gigs?limit=100", key)
    gigs = data.get("data", []) or data.get("gigs", [])

    # Score and filter
    candidates = [g for g in gigs
                  if g.get("id") not in contacted_ids
                  and g.get("status") == "active"
                  and float(g.get("budget_max") or 0) >= 10]
    candidates.sort(key=score, reverse=True)

    print(f"Gigs: {len(gigs)} | New candidates: {len(candidates)}")

    if not candidates:
        print("No new candidates — nothing to do.")
        return

    # Show top picks
    for g in candidates[:8]:
        s = score(g)
        b = g.get("budget_max")
        coin = g.get("payment_coin", "?")
        print(f"  [{s:2}] ${b} {coin} | {(g.get('title') or '')[:60]}")

    # Phase 1: Place bids (max CAP_BIDS)
    bids_placed = 0
    for g in candidates:
        if bids_placed >= CAP_BIDS:
            break
        gid = g["id"]
        bmax = float(g.get("budget_max") or 0)
        price = max(int(bmax), 10)
        title = g.get("title", "")
        poster = (g.get("poster") or {}).get("username", "there")

        # Build cover letter
        t = title.lower()
        if any(k in t for k in ("audit", "security", "smart contract", "review")):
            letter = (f"Hi {poster} — I'll deliver a rigorous {title} with findings, "
                      f"severity, fix recommendations, and clean evidence. 24-48h. ${price} fixed.")
        elif any(k in t for k in ("research", "brief", "analysis", "report")):
            letter = (f"Hi {poster} — I'll produce a source-cited {title} with verified "
                      f"citations, confidence labels, and practical recommendations. 24h. ${price} fixed.")
        elif any(k in t for k in ("python", "automation", "bot", "script", "api", "build")):
            letter = (f"Hi {poster} — I'll build and deliver the {title} as clean, tested "
                      f"Python — working code, install/run instructions, smoke test. 24-48h. ${price} fixed.")
        else:
            letter = (f"Hi {poster} — I'll take on the {title} end-to-end: clear deliverables, "
                      f"real evidence, fast async turnaround (24-48h). ${price} fixed.")

        try:
            r = api_post(f"/api/gigs/{gid}/apply", key,
                         {"cover_letter": letter, "proposed_price": price})
            app = r.get("application", r)
            print(f"✅ BID [{bids_placed+1}/{CAP_BIDS}] ${price} | {title[:50]}")
            state.setdefault("bids", []).append([gid, app.get("id", "")])
            bids_placed += 1
            time.sleep(65)  # ugig cooldown
        except Exception as e:
            print(f"❌ BID {gid[:8]}: {str(e)[:100]}")
            time.sleep(10)

    # Phase 2: DM high-value buyers directly (no cap except CAP_DMS)
    dms_sent = 0
    for g in candidates[bids_placed:]:
        if dms_sent >= CAP_DMS:
            break
        bmax = float(g.get("budget_max") or 0)
        if bmax < 50:  # Only DM for $50+ gigs
            continue

        gid = g["id"]
        poster_id = g.get("poster_id", "")
        poster = (g.get("poster") or {}).get("username", "there")
        title = g.get("title", "")

        if not poster_id:
            continue

        msg = (f"Hi {poster} — I saw your \"{title}\" gig (${bmax}) and can deliver this week. "
               f"I'm an AI automation studio (Singapore): Python, smart contracts, APIs, data pipelines. "
               f"I ship working code with tests + docs — 24-48h async. Interested? "
               f"Happy to do a small paid trial first.")

        try:
            r = api_post("/api/conversations", key,
                         {"recipient_id": poster_id, "gig_id": gid, "content": msg})
            print(f"💬 DM [{dms_sent+1}/{CAP_DMS}] ${bmax} | {title[:50]}")
            state.setdefault("dms", []).append([gid, poster_id])
            dms_sent += 1
            time.sleep(5)
        except Exception as e:
            print(f"❌ DM {gid[:8]}: {str(e)[:100]}")

    save_state(state)
    print(f"\nDone: {bids_placed} bids, {dms_sent} DMs")


if __name__ == "__main__":
    main()
