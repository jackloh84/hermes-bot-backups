#!/usr/bin/env python3
"""ugig.net pipeline — daily scan + bid on matching gigs + post our own gigs.

States:
1. NO_AUTH  — couldn't login, needs email confirm (send TG alert to Jack)
2. AUTH_OK  — can browse + bid + post gigs
3. AUTH_DEAD — token expired, need re-login

Files:
  - state/ugig_state.json (gigs we've seen, bids we've placed)
  - secrets/ugig.json (creds + token)
"""
import json, os, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://ugig.net"
SECRETS = Path("/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json")
STATE = Path("/home/ubuntu/.hermes/profiles/bot4/state/ugig_state.json")
LAST_ALERT = Path("/home/ubuntu/.hermes/profiles/bot4/state/ugig_last_alert.txt")
TG_CHAT = "366983738"

# Skills we can deliver (for matching)
SKILL_KEYWORDS = {
    "python": ["python", "script", "automation", "scraping", "data processing", "csv", "json", "excel"],
    "api": ["api", "endpoint", "rest", "graphql", "integration"],
    "ai": ["ai", "llm", "agent", "chatbot", "gpt", "claude", "automation"],
    "blockchain": ["smart contract", "solidity", "evm", "erc-20", "erc-721", "audit", "wallet"],
    "research": ["research", "competitor", "market analysis", "writing", "report"],
    "seo": ["seo", "audit", "meta tags", "backlinks", "search ranking"],
    "telegram": ["telegram", "bot", "channel"],
    "x402": ["x402", "usdc", "micropayment", "base"],
}


def http(method, path, body=None, token=None, hdrs=None):
    h = {"User-Agent": "KachangBot/1.0", "Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    if hdrs: h.update(hdrs)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=h, method=method)
    return urllib.request.urlopen(req, timeout=10)


def load_creds():
    if not SECRETS.exists():
        return None
    return json.load(open(SECRETS))


def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {"seen": {}, "bids": [], "daily_count": {}, "last_bid_ts": 0}


# Anti-ban rules per ugig.net ToS + good citizenship
MAX_BIDS_PER_DAY = 5
COOLDOWN_SECONDS = 60


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)


def get_tg_token():
    """Use Biz Bot (@her_a04_bot) for Jack DMs, not CS Bot."""
    p = "/home/ubuntu/.hermes/profiles/bot4/secrets/biz_bot.json"
    if not Path(p).exists():
        # Fallback to CS Bot if Biz Bot creds missing
        p = "/home/ubuntu/.hermes/profiles/cs-bot/.env"
    if not Path(p).exists(): return None
    if "biz_bot.json" in str(p):
        return json.load(open(p)).get("token")
    for line in open(p):
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def send_tg(text):
    token = get_tg_token()
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass


def score_gig(gig):
    """Return (score, matched_skills) — higher = better fit."""
    text = (gig.get("title", "") + " " + gig.get("description", "")).lower()
    score = 0
    matched = []
    for skill, keywords in SKILL_KEYWORDS.items():
        if any(k in text for k in keywords):
            score += 1
            matched.append(skill)
    # De-prioritize gigs we can't do
    bad = ["ios app", "android app", "native mobile", "hexagon", "game design", "subscribe", "promote hashtag"]
    for b in bad:
        if b in text:
            score -= 3
    return score, matched


def fetch_gigs(limit=50):
    try:
        r = http("GET", f"/api/gigs?limit={limit}")
        data = json.loads(r.read())
        return data.get("gigs", [])
    except Exception as e:
        print(f"fetch_gigs err: {e}", file=sys.stderr)
        return []


def main():
    creds = load_creds()
    if not creds:
        print("NO CREDS — signup needed")
        return

    # Prefer API key (no expiry) over JWT
    token = creds.get("api_key") or creds.get("token")
    if not token:
        print(f"NO TOKEN — email confirm needed for {creds.get('email')}")
        # Alert Jack once per day
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last = LAST_ALERT.read_text().strip() if LAST_ALERT.exists() else ""
        if last != today:
            send_tg(f"📧 ugig.net signup needs email confirmation.\n\nEmail: {creds.get('email')}\nPassword: {creds.get('password')}\nUsername: {creds.get('username')}\n\nCheck Gmail on iPhone, tap 'Confirm email' link, then reply 'ugig ok' so I can resume.")
            LAST_ALERT.write_text(today)
        return

    gigs = fetch_gigs(50)
    state = load_state()
    seen = state.setdefault("seen", {})

    new_gigs = []
    best_matches = []
    for g in gigs:
        gid = g["id"]
        if gid not in seen:
            new_gigs.append(g)
            seen[gid] = {"first_seen": datetime.now(timezone.utc).isoformat(), "title": g.get("title","")[:80]}
        score, skills = score_gig(g)
        if score >= 2:
            best_matches.append((score, skills, g))

    save_state(state)

    # Report
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = [f"🔍 ugig.net scan — {now}", f"Total gigs: {len(gigs)} | New: {len(new_gigs)} | Good matches (score≥2): {len(best_matches)}"]
    if new_gigs:
        msg.append("\nNEW GIGS:")
        for g in new_gigs[:5]:
            score, skills = score_gig(g)
            msg.append(f"  • [{score}] {g.get('title','')[:80]}")
            msg.append(f"    skills: {', '.join(skills)}")
    if best_matches:
        msg.append("\nTOP 5 BEST FITS:")
        for score, skills, g in sorted(best_matches, key=lambda x: -x[0])[:5]:
            msg.append(f"  • [{score}] {g.get('title','')[:80]}")
            msg.append(f"    {g['id']} | skills: {', '.join(skills)}")
            msg.append(f"    {BASE}/gigs/{g['id']}")

    # Anti-ban: rate-limit alerts based on bids/day
    import datetime as _dt
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    bids_today = state.get("daily_count", {}).get(today, 0)
    if bids_today >= MAX_BIDS_PER_DAY:
        msg += f"\n\n⚠️ Daily bid cap reached ({bids_today}/{MAX_BIDS_PER_DAY}) — Biz Bot will pause auto-bidding until tomorrow. Surface new matches to Jack for manual review only."

    print("\n".join(msg))

    # Alert TG only if there are NEW high-score matches
    if best_matches and new_gigs:
        send_tg("\n".join(msg[:20]))


if __name__ == "__main__":
    main()