#!/usr/bin/env python3
"""
BountyBook CLI for Biz Bot — Find bounties, claim work, submit output, get paid in USDC.
Usage: python3 bountybook.py <command> [args]

Commands:
  list          — List open bounties
  claim <id>    — Claim a bounty by ID
  submit <id>   — Submit output for a bounty (reads from stdin)
  profile       — Show agent reputation/profile
  nonce         — Get auth nonce
"""
import json, os, sys, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API = "https://api.bountybook.ai"
WALLET = os.environ.get("BOUNTYBOOK_WALLET_ADDRESS", "0xD2965001942B7BE86143510dB9945875301e639b")
TOKEN_FILE = "/tmp/bountybook_token.json"

def api_get(path):
    req = Request(f"{API}{path}", headers={"User-Agent": "BizBot/1.0"})
    return json.loads(urlopen(req, timeout=15).read())

def api_auth_get(path, token):
    req = Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}", "User-Agent": "BizBot/1.0"})
    return json.loads(urlopen(req, timeout=15).read())

def get_token():
    if os.path.exists(TOKEN_FILE):
        data = json.load(open(TOKEN_FILE))
        if data.get("expires_at", 0) > time.time() + 60:
            return data["token"]
    # Get nonce
    nonce_data = api_get(f"/auth/nonce?address={WALLET}")
    nonce = nonce_data.get("nonce", "")
    if not nonce:
        print("{\"error\":\"no nonce\"}")
        sys.exit(1)
    # Sign with private key
    import subprocess
    pk = os.environ.get("BOUNTYBOOK_PRIVATE_KEY", "")
    if not pk:
        print("{\"error\":\"BOUNTYBOOK_PRIVATE_KEY not set\"}")
        sys.exit(1)
    # Use node to sign (viem)
    js_code = f'''
    const {{ privateKeyToAccount }} = await import("viem/accounts");
    const account = privateKeyToAccount("{pk}");
    const sig = await account.signMessage({{ message: "{nonce}" }});
    console.log(JSON.stringify({{ signature: sig, address: account.address }}));
    '''
    result = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f'{{"error":"sign failed: {result.stderr.strip()}"}}')
        sys.exit(1)
    sig_data = json.loads(result.stdout)
    
    # Verify
    req = Request(f"{API}/auth/verify", 
                  data=json.dumps({"address": sig_data["address"], "signature": sig_data["signature"]}).encode(),
                  headers={"Content-Type": "application/json", "User-Agent": "BizBot/1.0"})
    auth = json.loads(urlopen(req, timeout=15).read())
    
    token = auth.get("token", "")
    expires = auth.get("expiresAt", time.time() + 3600)
    json.dump({"token": token, "expires_at": expires}, open(TOKEN_FILE, "w"))
    return token

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    
    if cmd == "list":
        limit = sys.argv[2] if len(sys.argv) > 2 else "10"
        data = api_get(f"/jobs?status=open&limit={limit}")
        print(json.dumps(data, indent=2))
    
    elif cmd == "claim":
        if len(sys.argv) < 3:
            print('{"error":"usage: claim <job_id>"}')
            sys.exit(1)
        job_id = sys.argv[2]
        token = get_token()
        req = Request(f"{API}/jobs/{job_id}/claim",
                      data=json.dumps({"executorAddress": WALLET}).encode(),
                      headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}", "User-Agent": "BizBot/1.0"})
        try:
            result = json.loads(urlopen(req, timeout=15).read())
            print(json.dumps(result, indent=2))
        except HTTPError as e:
            print(json.dumps({"error": f"HTTP {e.code}", "body": e.read().decode()}, indent=2))
    
    elif cmd == "submit":
        if len(sys.argv) < 3:
            print('{"error":"usage: submit <job_id>"}')
            sys.exit(1)
        job_id = sys.argv[2]
        output_data = json.loads(sys.stdin.read())
        token = get_token()
        req = Request(f"{API}/jobs/{job_id}/submit",
                      data=json.dumps({"executorAddress": WALLET, "outputData": output_data}).encode(),
                      headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}", "User-Agent": "BizBot/1.0"})
        try:
            result = json.loads(urlopen(req, timeout=15).read())
            print(json.dumps(result, indent=2))
        except HTTPError as e:
            print(json.dumps({"error": f"HTTP {e.code}", "body": e.read().decode()}, indent=2))
    
    elif cmd == "profile":
        data = api_get(f"/reputation/{WALLET}")
        print(json.dumps(data, indent=2))
    
    elif cmd == "nonce":
        data = api_get(f"/auth/nonce?address={WALLET}")
        print(json.dumps(data, indent=2))
    
    else:
        print(f'{{"error":"unknown command: {cmd}"}}')
