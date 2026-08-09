#!/usr/bin/env python3
"""Poll Virtuals ACP CLI token after Jack approves the auth URL. Saves token to secrets/acp_token.json."""
import json, time, urllib.request, os

REQUEST_ID = "3abe30cf84f62d235cb799e3bd72084d"
URL = f"https://api.acp.virtuals.io/auth/cli/token?requestId={REQUEST_ID}"
OUT = "/home/ubuntu/.hermes/profiles/bot4/secrets/acp_token.json"
UA = {"User-Agent": "BizBot/1.0"}

for i in range(60):  # up to 5 min
    try:
        req = urllib.request.Request(URL, headers=UA)
        r = json.loads(urllib.request.urlopen(req, timeout=10).read())
        inner = r.get("data", r)
        if inner.get("token") or inner.get("accessToken"):
            json.dump(inner, open(OUT, "w"), indent=1)
            os.chmod(OUT, 0o600)
            print(f"✅ ACP TOKEN SAVED: wallet={inner.get('walletAddress') or inner.get('wallet')}")
            raise SystemExit(0)
        print(f"[{i}] waiting... {str(r)[:100]}")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[{i}] err: {str(e)[:100]}")
    time.sleep(5)
print("TIMEOUT — no token within 5 min (Jack didn't click, or auth URL expired)")
