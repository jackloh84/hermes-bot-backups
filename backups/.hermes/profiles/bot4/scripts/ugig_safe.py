#!/usr/bin/env python3
"""ugig.net anti-ban guard + smart bidding.

Limits per the ToS + good citizenship:
- 10 active gigs max (we have 1)
- Max 5 bids per day
- Max 2 bids on same poster per day
- 30-second cooldown between bids
- Score ≥ 3 minimum match
- Diverse cover letters (no template reuse)
"""
import json, time, hashlib, re
from pathlib import Path

STATE = Path("/home/ubuntu/.hermes/profiles/bot4/state/ugig_state.json")
LIMITS = {
    "max_bids_per_day": 5,
    "max_bids_same_poster_per_day": 2,
    "min_seconds_between_bids": 30,
    "min_score_match": 3,
    "max_active_gigs": 10,
}

def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {"bids": [], "daily_count": {}, "poster_daily_count": {}, "last_bid_ts": 0}

def save_state(s):
    json.dump(s, open(STATE, "w"), indent=2)

def can_bid(state, gig, now_ts):
    """Returns (can_bid: bool, reason: str)."""
    # Cooldown
    elapsed = now_ts - state.get("last_bid_ts", 0)
    if elapsed < LIMITS["min_seconds_between_bids"]:
        return False, f"cooldown ({LIMITS["min_seconds_between_bids"]-elapsed}s left)"
    
    # Already bid on this gig?
    for gig_id, _ in state.get("bids", []):
        if gig_id == gig["id"]:
            return False, "already bid on this gig"
    
    # Daily cap
    today = time.strftime("%Y-%m-%d")
    daily = state.get("daily_count", {}).get(today, 0)
    if daily >= LIMITS["max_bids_per_day"]:
        return False, f"daily cap hit ({LIMITS["max_bids_per_day"]})"
    
    # Same-poster cap
    poster_id = gig.get("poster_id", "")
    poster_count = state.get("poster_daily_count", {}).get(f"{today}|{poster_id}", 0)
    if poster_count >= LIMITS["max_bids_same_poster_per_day"]:
        return False, f"same-poster cap hit ({LIMITS["max_bids_same_poster_per_day"]})"
    
    return True, "OK"

def record_bid(state, gig):
    today = time.strftime("%Y-%m-%d")
    poster_id = gig.get("poster_id", "")
    state.setdefault("daily_count", {})
    state["daily_count"][today] = state["daily_count"].get(today, 0) + 1
    state.setdefault("poster_daily_count", {})
    state["poster_daily_count"][f"{today}|{poster_id}"] = state["poster_daily_count"].get(f"{today}|{poster_id}", 0) + 1
    state["last_bid_ts"] = int(time.time())
    return state

def cover_letter_hash(letter):
    """Hash cover letter to detect template reuse."""
    norm = re.sub(r"[^a-z0-9]", "", letter.lower())
    return hashlib.md5(norm.encode()).hexdigest()[:8]

def check_letter_diversity(state, cover_letter):
    """Reject if we've sent the same cover letter recently."""
    h = cover_letter_hash(cover_letter)
    recent_hashes = state.get("recent_letter_hashes", [])
    if h in recent_hashes[-10:]:  # last 10 letters
        return False, "duplicate cover letter detected"
    state.setdefault("recent_letter_hashes", []).append(h)
    if len(state["recent_letter_hashes"]) > 50:
        state["recent_letter_hashes"] = state["recent_letter_hashes"][-50:]
    return True, "OK"
