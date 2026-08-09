#!/usr/bin/env python3
"""BountyBook monitor — only fires when (a) any new confirmed payout appears,
   or (b) jobs_failed increments for our wallet. No gas burn, no claim attempts."""
import json, time, urllib.request

WALLET = "0xD2965001942B7BE86143510dB9945875301e639b"
API = "https://api.bountybook.ai"


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BizBot/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get_agent():
    return http_get(f"{API}/agents/{WALLET}")


def get_recent_verified(limit=100):
    return http_get(f"{API}/jobs?status=verified&limit={limit}")


def main():
    print("[bb-monitor] starting, polling every 30 min (no API spam)", flush=True)
    last_failed = None
    last_confirmed_total = None
    while True:
        try:
            agent = get_agent()
            failed = agent.get("jobs_failed", 0)
            earned = agent.get("total_earned", 0)

            verified = get_recent_verified(50)
            confirmed_count = sum(1 for j in verified.get("jobs", []) if j.get("payout_status") == "confirmed")

            if last_failed is None:
                last_failed = failed
                last_confirmed_total = confirmed_count
                print(f"[init] jobs_failed={failed} total_earned={earned} confirmed_payouts_on_platform={confirmed_count}/50", flush=True)
            else:
                if confirmed_count > last_confirmed_total:
                    delta = confirmed_count - last_confirmed_total
                    print(f"[RECOVERY] platform now has {confirmed_count}/{len(verified.get('jobs',[]))} confirmed payouts (+{delta}). BountyBook payouts may be working again.", flush=True)
                    last_confirmed_total = confirmed_count
                elif failed > last_failed:
                    print(f"[WARN] my jobs_failed: {last_failed} -> {failed}", flush=True)
                    last_failed = failed

        except Exception as e:
            print(f"[poll error] {e}", flush=True)
        time.sleep(1800)  # 30 minutes


if __name__ == "__main__":
    main()