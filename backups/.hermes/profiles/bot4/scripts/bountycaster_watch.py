#!/usr/bin/env python3
"""Bountycaster watcher — silent watchdog.
Prints ONLY when open bounties appear. Empty stdout = nothing to report.
"""
import json, urllib.request

URL = "https://www.bountycaster.xyz/api/v1/bounties/open"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"}


def main():
    try:
        req = urllib.request.Request(URL, headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        print(f"[BOUNTYCASTER ERR] {e}")
        return

    bounties = data.get("bounties", [])
    if bounties:
        print(f"🪙 BOUNTYCASTER — {len(bounties)} open bounties!")
        for b in bounties[:10]:
            title = b.get("title") or b.get("name") or "?"
            amt = b.get("amount") or b.get("reward") or "?"
            print(f"  - {title} ({amt})")
        print("\nCheck: https://www.bountycaster.xyz — Farcaster USDC bounties, 0% fee.")


if __name__ == "__main__":
    main()
