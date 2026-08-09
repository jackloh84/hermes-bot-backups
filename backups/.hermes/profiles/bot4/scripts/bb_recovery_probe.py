#!/usr/bin/env python3
"""BountyBook recovery probe — silent watchdog.
Runs via cron. Prints ONLY when a re-activation signal is detected:
  - treasury_usdc >= 50
  - any job with status=paid
  - a new open job created in the last 7 days
Empty stdout = nothing to report = no message sent (watchdog pattern).
"""
import json, sys, urllib.request
from datetime import datetime, timezone

API = "https://api.bountybook.ai"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"}


def get(path):
    req = urllib.request.Request(API + path, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def main():
    signals = []
    try:
        health = get("/health")
        escrow = health.get("escrow", {})
        treasury = escrow.get("treasury_usdc", 0)
        failed = escrow.get("failed_payouts", 0)
        if treasury >= 50:
            signals.append(f"💰 TREASURY REFILLED: ${treasury:.2f} (was $0.965)")
    except Exception as e:
        print(f"[BB PROBE ERR] /health: {e}")
        return

    try:
        paid = get("/jobs?status=paid&limit=5").get("jobs", [])
        if paid:
            signals.append(f"✅ PAID JOB FOUND: {len(paid)} job(s) reached status=paid — payout system alive!")
            for j in paid[:3]:
                signals.append(f"   - {j.get('title', '?')} ${j.get('budget_usdc', '?')}")
    except Exception as e:
        print(f"[BB PROBE ERR] paid: {e}")
        return

    try:
        open_jobs = get("/jobs?status=open&limit=50").get("jobs", [])
        now = datetime.now(timezone.utc)
        fresh = []
        for j in open_jobs:
            ts = j.get("created_at")
            if isinstance(ts, (int, float)):
                age_days = (now.timestamp() - ts) / 86400
                if age_days < 7:
                    fresh.append(j)
        if fresh:
            signals.append(f"🆕 NEW BOUNTIES: {len(fresh)} open job(s) created in last 7 days (platform active again)")
            for j in fresh[:3]:
                signals.append(f"   - {j.get('title', '?')} ${j.get('budget_usdc', '?')}")
    except Exception as e:
        print(f"[BB PROBE ERR] open: {e}")
        return

    if signals:
        print("🚨 BOUNTYBOOK RECOVERY SIGNAL 🚨")
        print("\n".join(signals))
        print("\nNext step: run the earn-playbook in bountybook-earnings skill (claim small code jobs, volume strategy).")


if __name__ == "__main__":
    main()
