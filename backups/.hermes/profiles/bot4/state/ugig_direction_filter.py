#!/usr/bin/env python3
import json, urllib.request, urllib.error, re
from datetime import datetime, timezone

SECRETS = "/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json"
d = json.load(open(SECRETS))
api_key = d["api_key"]

def get(url):
    req = urllib.request.Request(url, headers={"X-API-Key": api_key, "User-Agent": "KachangBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

gigs = get("https://ugig.net/api/gigs?limit=100&sort=newest")
glist = gigs.get("gigs", gigs.get("data", [])) if isinstance(gigs, dict) else (gigs or [])

apps = get("https://ugig.net/api/applications/my")
alist = apps.get("applications", apps.get("data", [])) if isinstance(apps, dict) else (apps or [])
applied_ids = set()
for a in alist:
    gid = a.get("gig_id") or (a.get("gig") or {}).get("id")
    if gid:
        applied_ids.add(gid)

# our user id from secrets
my_id = d.get("user_id")

# seller markers
SELLER_MARKERS = [
    "FOR-HIRE SERVICE OFFER", "this is not a request for another worker",
    "please do not submit applications", "buyers: message me", "message me or hire",
    "i will build", "i will deliver", "i deliver", "i will diagnose", "i diagnose",
    "i will write", "i will turn", "i will rescue", "i will audit", "i will analyze",
    "i analyze", "i crawl your public site", "fixed price:", "autonomous-agent service",
    "autonomous agent service", "transparent a", "livrable", "i will take", "what you get",
    "public proof", "public demo", "i capture", "i check", "i clean", "you get a complete",
    "deliverables:", "i will produce",
]
VCC_MARKERS = ["virtual card", "virtual credit", "virtual payment", "reloadable", "vccbusiness"]

def is_seller(desc):
    dl = desc.lower()
    hits = [m for m in SELLER_MARKERS if m in dl]
    return hits

def is_vcc(desc, title, budget_min):
    if budget_min == 0 or (budget_min == 0 and budget_min is not None):
        pass
    dl = (desc + " " + title).lower()
    if any(m in dl for m in VCC_MARKERS):
        return True
    if (budget_min or 0) == 0:
        return True
    return False

print(f"POOL={len(glist)} APPLIED={len(applied_ids)} MYID={my_id}")
print()

candidates = []
for g in glist:
    gid = g.get("id")
    title = g.get("title", "")
    desc = g.get("description", "") or ""
    budget_min = g.get("budget_min") or 0
    poster = (g.get("poster") or {}).get("username")
    poster_id = g.get("poster_id")
    own = (poster_id == my_id) or (poster == "kachangsia")
    applied = gid in applied_ids
    seller_hits = is_seller(desc)
    vcc = is_vcc(desc, title, budget_min)
    status = g.get("status")
    listing = g.get("listing_type")

    flags = []
    if own: flags.append("OWN")
    if applied: flags.append("APPLIED")
    if seller_hits: flags.append(f"SELLER[{seller_hits[0]}]")
    if vcc: flags.append("VCC/SPAM")
    if status != "active": flags.append(f"status={status}")
    if listing != "hiring": flags.append(f"listing={listing}")

    if not flags:
        candidates.append(g)
        print(f"*** GENUINE-BUYER CANDIDATE ***")
        print(f"  id={gid}  budget=${budget_min}-{g.get('budget_max')}  poster={poster}")
        print(f"  title={title}")
        print(f"  desc={desc[:300]}")
        print()

print("="*70)
print(f"RESULT: {len(candidates)} genuine-buyer candidates (no OWN/APPLIED/SELLER/VCC flags)")

# Also summarize the pool composition
own_n = sum(1 for g in glist if (g.get("poster") or {}).get("username")=="kachangsia")
vcc_n = sum(1 for g in glist if is_vcc(g.get("description",""), g.get("title",""), g.get("budget_min") or 0))
seller_n = sum(1 for g in glist if is_seller(g.get("description","")))
applied_in_pool = sum(1 for g in glist if g.get("id") in applied_ids)
print(f"pool: own={own_n} vcc/spam={vcc_n} seller-offers={seller_n} already-applied={applied_in_pool}")
print(f"not-applied in pool: {sum(1 for g in glist if g.get('id') not in applied_ids)}")
