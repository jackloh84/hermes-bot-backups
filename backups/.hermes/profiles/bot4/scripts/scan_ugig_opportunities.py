#!/usr/bin/env python3
"""ugig.net WORKER-side opportunity scan (cron).

Checks three things and reports EARNING opportunities only:
  1. Notifications — unread count + key alerts (new_message / application_status / payment_received).
  2. New gigs where OTHERS are hiring (buyer-side) matching Python/AI/x402/security stack,
     that we have NOT already applied to.
  3. New messages from buyers in conversations we're part of.

Skips: seller/for-hire offers, invoice/payment-request noise (anything asking US to pay).
"""
import json, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://ugig.net"
SECRETS = Path("/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json")
STATE = Path("/home/ubuntu/.hermes/profiles/bot4/state/ugig_state.json")

d = json.load(open(SECRETS))
KEY = d["api_key"]
MY_UID = d.get("user_id", "")

H = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (KachangBot/1.0)",
}

# ---- stack we can deliver (worker) ----
STACK_KEYWORDS = {
    "python": ["python", "script", "automation", "scrape", "scraping", "data process", "csv", "json", "excel", "pandas", "bot"],
    "api": ["api", "rest", "graphql", "endpoint", "integration", "webhook"],
    "ai": ["ai", "llm", "agent", "chatbot", "gpt", "claude", "rag", "openai", "model"],
    "x402": ["x402", "usdc", "micropayment", "coinpay", "base chain", "8453"],
    "security": ["security", "audit", "vulnerab", "cwe", "exploit", "smart contract", "solidity", "evm", "review", "penetration"],
}

# ---- direction detection (listing_type is unreliable; description is truth) ----
BUYER_SIGNALS = [
    "i need", "we need", "need help", "help me", "i want", "we want",
    "looking for", "looking to", "seeking", "need a", "need an", "need someone",
    "build me", "build for me", "for my", "hiring", "hire", "want someone",
    "i'm looking", "i am looking", "need someone", "can you", "who can", "wanted",
]
SELLER_SIGNALS = [
    "i will", "i can", "for-hire", "for hire", "autonomous agent service",
    "i ship", "i offer", "i provide", "i am offering", "i'm offering",
    "service offer", "i build", "i create", "i write", "i deliver", "i do ",
    "my gig", "i'm a", "i am a", "we are a", "we offer", "we provide", "we build",
    "i will build", "i will write", "i will create", "i will deliver",
]
NOISE_KEYWORDS = [
    "virtual card", "vcc", "reloadable", "subscribe to my", "promote this hashtag",
    "buyer-side", "invoice", "payment request", "top up", "resend usdc",
]

# ---- small HTTP helpers ----
def http_get(path, timeout=25):
    req = urllib.request.Request(f"{BASE}{path}", headers=H)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def safe_list(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    inner = data.get("data", data)
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict):
        for k in ("gigs", "applications", "notifications", "messages", "posts", "items", "data"):
            if isinstance(inner.get(k), list):
                return inner[k]
    return []

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def main():
    state = json.load(open(STATE)) if STATE.exists() else {}
    seen = state.setdefault("seen", {})
    conv_track = state.setdefault("conv_last_seen", {})  # conv_id -> ts of last buyer msg we've seen
    report = []
    errors = []

    # ============ 1. NOTIFICATIONS ============
    unread = 0
    key_alerts = []
    try:
        nd = http_get("/api/notifications?limit=50")
        unread = (nd.get("data", {}).get("unread_count") if isinstance(nd.get("data"), dict) else None) or nd.get("unread_count") or 0
        notifs = safe_list(nd)
        for n in notifs:
            typ = n.get("type", "")
            title = (n.get("title") or "")
            body = (n.get("body") or "")[:160]
            created = n.get("created_at", "")
            # skip buyer-side invoice / payment-request noise
            blob = (title + " " + body).lower()
            if any(k in blob for k in NOISE_KEYWORDS):
                continue
            # only UNREAD alerts matter for a scan — old history is not an opportunity
            if n.get("read_at"):
                continue
            if typ in ("new_message", "application_status", "payment_received", "new_application", "gig_hired"):
                key_alerts.append((typ, created, title, body))
    except Exception as e:
        errors.append(f"notifications: {str(e)[:120]}")

    # ============ 2. GIGS (buyer hiring, matching stack, not applied) ============
    my_app_gig_ids = set()
    try:
        apps = safe_list(http_get("/api/applications/my?limit=200"))
        for a in apps:
            if a.get("gig_id"):
                my_app_gig_ids.add(a["gig_id"])
    except Exception:
        pass
    bid_ids = {b[0] for b in state.get("bids", [])}
    my_gig_ids = set(state.get("my_gigs", []))
    already = bid_ids | my_app_gig_ids | my_gig_ids

    all_gigs = {}
    for sort in ("newest", "budget_high"):
        try:
            for g in safe_list(http_get(f"/api/gigs?sort={sort}&limit=100")):
                all_gigs[g["id"]] = g
        except Exception as e:
            errors.append(f"gigs {sort}: {str(e)[:120]}")

    new_buyer_matches = []   # (score, gig) — new & matching & not applied
    known_matches = []       # matching buyer gigs we already applied to (context)
    for gid, g in all_gigs.items():
        title = g.get("title") or ""
        desc = g.get("description") or ""
        blob = (title + " " + desc).lower()
        if any(k in blob for k in NOISE_KEYWORDS):
            continue
        is_buyer = any(s in blob for s in BUYER_SIGNALS) and not any(s in blob for s in SELLER_SIGNALS)
        if not is_buyer:
            continue
        score = 0
        matched = []
        for skill, kws in STACK_KEYWORDS.items():
            if any(k in blob for k in kws):
                score += 1
                matched.append(skill)
        if score < 2:
            continue
        bmax = g.get("budget_max") or 0
        entry = {
            "id": gid,
            "title": title[:100],
            "budget": f"${bmax}" if bmax else "?",
            "skills": matched,
            "poster": (g.get("poster") or {}).get("username", "?"),
            "url": f"{BASE}/gigs/{gid}",
            "score": score,
        }
        if gid in already:
            known_matches.append(entry)
        elif gid not in seen:
            new_buyer_matches.append(entry)
            seen[gid] = {"first_seen": now_iso(), "title": title[:80]}
        # else: seen but not applied -> surfaced previously; leave alone

    new_buyer_matches.sort(key=lambda x: (-x["score"], -(x["budget"] != "?" and float(str(x["budget"]).lstrip("$") or 0) or 0)))

    # ============ 3. CONVERSATIONS (new buyer messages) ============
    new_replies = []
    try:
        convs = safe_list(http_get("/api/conversations?limit=100"))
        for c in convs:
            cid = c.get("id")
            if not cid:
                continue
            # participant map sender_id -> username (participants order is NOT meaningful)
            pmap = {}
            for p in (c.get("participants") or []):
                if isinstance(p, dict) and p.get("id"):
                    pmap[p["id"]] = p.get("username") or "?"
            c_unread = c.get("unread_count") or 0
            try:
                msgs = safe_list(http_get(f"/api/conversations/{cid}/messages?limit=20"))
            except Exception:
                msgs = []
            # fall back to last_message envelope if thread fetch failed
            if not msgs and isinstance(c.get("last_message"), dict):
                lm = c["last_message"]
                msgs = [{"sender_id": lm.get("sender_id"), "content": lm.get("content"),
                         "created_at": c.get("last_message_at") or lm.get("created_at")}]
            if not msgs:
                if c_unread > 0:
                    new_replies.append({"conv_id": cid, "buyer": "?", "preview": f"[unread_count={c_unread}] fetch failed",
                                        "ts": "", "unread": c_unread})
                continue
            # newest message in the thread decides: buyer has floor only if the
            # LAST message was sent by a buyer (not us). Historical buyer messages
            # we already answered are NOT opportunities.
            newest = max(msgs, key=lambda m: m.get("created_at") or "")
            newest_ts = newest.get("created_at") or ""
            newest_sender = newest.get("sender_id")
            conv_track[cid] = max(conv_track.get(cid, ""), newest_ts)
            if newest_sender and newest_sender != MY_UID:
                blob = (newest.get("content") or "").lower()
                if any(k in blob for k in NOISE_KEYWORDS):
                    continue  # invoice / payment-request noise — skip
                new_replies.append({
                    "conv_id": cid,
                    "buyer": pmap.get(newest_sender, "?"),
                    "preview": (newest.get("content") or "")[:180],
                    "ts": newest_ts,
                    "unread": c_unread,
                })
    except Exception as e:
        errors.append(f"conversations: {str(e)[:120]}")

    # ============ SAVE STATE ============
    state["last_scan_at"] = now_iso()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE, "w"), indent=2)

    # ============ REPORT ============
    lines = []
    lines.append(f"🔍 ugig.net worker-scan — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Notifications: {unread} unread | New buyer gigs (match, not applied): {len(new_buyer_matches)} | New buyer replies: {len(new_replies)}")

    if key_alerts:
        lines.append("\n— KEY ALERTS (notifications) —")
        for typ, created, title, body in key_alerts[:8]:
            lines.append(f"  [{typ}] {created[:16]} {title} :: {body}")

    if new_buyer_matches:
        lines.append("\n— NEW BUYER GIGS (apply window) —")
        for e in new_buyer_matches[:10]:
            lines.append(f"  • [{e['score']}] {e['title']} | {e['budget']} | by {e['poster']}")
            lines.append(f"    skills: {', '.join(e['skills'])} | {e['url']}")
        if len(new_buyer_matches) > 10:
            lines.append(f"  … +{len(new_buyer_matches)-10} more")

    if new_replies:
        lines.append("\n— BUYER REPLIES (respond fast) —")
        for r in new_replies:
            lines.append(f"  • {r['buyer']} ({r['conv_id'][:8]}) {r['ts'][:16]}: {r['preview']}")

    if known_matches:
        lines.append("\n— MATCHING BUYER GIGS ALREADY APPLIED (context) —")
        for e in known_matches[:5]:
            lines.append(f"  • {e['title']} | {e['budget']} | {e['url']}")

    if errors:
        lines.append("\n⚠️ errors: " + "; ".join(errors))

    print("\n".join(lines))

    # marker for cron: nothing new at all?
    if not key_alerts and not new_buyer_matches and not new_replies and not errors:
        print("\nNO_NEW_OPPORTUNITIES")

if __name__ == "__main__":
    main()
