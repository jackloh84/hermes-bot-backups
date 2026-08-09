#!/usr/bin/env python3
"""Overnight ugig watch — polls the Client Kit $200 conversation + notifications.
Silent watchdog: prints ONLY when something needs action (new message from Client Kit,
application accepted, new notifications). Empty stdout = nothing to report.
"""
import json, urllib.request

KEY_PATH = "/home/ubuntu/.hermes/profiles/bot4/secrets/ugig.json"
CONV_ID = "27423df6-7850-4ae0-9056-483cd00f3394"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
      "X-API-Key": ""}


def main():
    try:
        key = json.load(open(KEY_PATH)).get("api_key", "")
    except Exception as e:
        print(f"[UGIG WATCH ERR] no api key: {e}")
        return
    UA["X-API-Key"] = key

    # 1. Check conversation for new messages
    try:
        req = urllib.request.Request(
            f"https://ugig.net/api/conversations/{CONV_ID}/messages",
            headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        msgs = data.get("data", [])
        if msgs:
            last = msgs[-1]
            who = last.get("sender", {}).get("full_name") or "?"
            content = (last.get("content") or "")[:200]
            # Only alert if last message is NOT from us (i.e. Client Kit replied)
            our_id = "6ed16182-8c12-4255-a3ad-27b4a3faf3a9"
            if last.get("sender_id") != our_id:
                print(f"💬 NEW from {who}: {content}")
                print(f"\nReply: POST /api/conversations/{CONV_ID}/messages")
    except Exception as e:
        print(f"[UGIG WATCH ERR] conv: {e}")
        return

    # 2. Check notifications
    try:
        req = urllib.request.Request("https://ugig.net/api/notifications", headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        notifs = data.get("notifications") or data.get("data") or []
        unread = [n for n in notifs if not n.get("read")]
        if unread:
            for n in unread[:5]:
                print(f"🔔 {n.get('type', '?')}: {(n.get('body') or n.get('message') or '')[:120]}")
    except Exception as e:
        pass  # notifications optional


if __name__ == "__main__":
    main()
