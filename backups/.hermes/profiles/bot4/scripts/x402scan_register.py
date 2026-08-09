#!/usr/bin/env python3
"""Register api.kachangsia.com on x402scan via SIWX (EIP-191 SIWE) — exact @x402/extensions format."""
import json, base64, os, urllib.request
from eth_account import Account
from eth_account.messages import encode_defunct

ENDPOINT = "https://www.x402scan.com/api/x402/registry/register-origin"
ORIGIN = "https://api.kachangsia.com"
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

def load_env():
    env = {}
    for f in ["/home/ubuntu/.hermes/.env", "/home/ubuntu/.hermes/profiles/bot4/.env"]:
        if os.path.exists(f):
            for line in open(f):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def post(url, body, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**UA, **(headers or {})}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}

def main():
    env = load_env()
    acct = Account.from_key(env["WALLET_PK"])
    print("wallet:", acct.address)

    code, ch = post(ENDPOINT, {"origin": ORIGIN})
    info = ch.get("extensions", {}).get("sign-in-with-x", {}).get("info", {})
    if not info:
        print("no challenge:", json.dumps(ch)[:200]); return

    # SIWE (EIP-4361) message — exact siwe.prepareMessage() format
    chain_id = info["chainId"].split(":")[1]  # eip155:8453 -> 8453
    msg = (
        f"{info['domain']} wants you to sign in with your Ethereum account:\n"
        f"{acct.address}\n\n"
        f"{info.get('statement', '')}\n\n"
        f"URI: {info['uri']}\n"
        f"Version: {info.get('version', '1')}\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {info['nonce']}\n"
        f"Issued At: {info['issuedAt']}\n"
        f"Expiration Time: {info.get('expirationTime', '')}"
    )
    sig = "0x" + Account.sign_message(encode_defunct(text=msg), acct.key).signature.hex()

    payload = {
        "domain": info["domain"],
        "address": acct.address,
        "statement": info.get("statement"),
        "uri": info["uri"],
        "version": info.get("version", "1"),
        "chainId": info["chainId"],
        "type": info.get("type"),
        "nonce": info["nonce"],
        "issuedAt": info["issuedAt"],
        "expirationTime": info.get("expirationTime"),
        "signature": sig,
    }
    # safeBase64Encode = STANDARD base64 (with padding), not urlsafe
    enc = base64.b64encode(json.dumps(payload).encode()).decode()
    print("siwx header len:", len(enc))

    for name, hdr in [("sign-in-with-x", enc), ("x-sign-in-with-x", enc)]:
        c2, r2 = post(ENDPOINT, {"origin": ORIGIN}, {hdr: enc})
        print(f"[{name}] HTTP {c2}: {json.dumps(r2)[:300]}")
        if c2 in (200, 201):
            print("✅ REGISTERED"); return

if __name__ == "__main__":
    main()
