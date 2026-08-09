#!/usr/bin/env python3
"""
Virtuals ACP client — handles P-256 (secp256r1) signer authentication.

Loads the private key from /home/ubuntu/.hermes/profiles/bot4/secrets/virtuals_acp_signer.der
(chmod 600). Never logs the key. Never echoes key bytes.

Usage:
    python3 acp_client.py <command> [args]

Commands:
    auth          — Mint a JWT via /auth/agent, print + cache
    browse <q>    — Search active v2 agents with offerings
    test-job      — Claim Rai AI quick_code_review ($0.05, 5min) as a smoke test
    balance       — Check USDC balance on Base
"""
import json, os, sys, time, base64, urllib.request, urllib.error

# ─── Security ───
KEY_FILE = "/home/ubuntu/.hermes/profiles/bot4/secrets/virtuals_acp_signer.der"
WALLET = os.environ.get("ACP_WALLET", "0x13B5B41DD68e950e021DBA99dF65bF849d84cDcF")
API = "https://api.acp.virtuals.io"
TOKEN_FILE = "/tmp/acp_token.json"
LOG_FILE = "/home/ubuntu/.hermes/profiles/bot4/state/acp_activity.log"


def _log(msg):
    """Append-only activity log. Never logs keys."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")


def load_key():
    """Load P-256 private key from chmod-600 file. Returns cryptography key object."""
    if not os.path.exists(KEY_FILE):
        sys.exit(f"ERROR: key file not found: {KEY_FILE}")
    mode = oct(os.stat(KEY_FILE).st_mode)[-3:]
    if mode != "600":
        sys.exit(f"ERROR: key file must be chmod 600 (got {mode}): {KEY_FILE}")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    with open(KEY_FILE, "rb") as f:
        der_bytes = f.read()
    return serialization.load_der_private_key(der_bytes, password=None, backend=default_backend())


def sign_message(priv, message: bytes) -> bytes:
    """Sign message with P-256 + SHA256. Returns DER signature."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    return priv.sign(message, ec.ECDSA(hashes.SHA256()))


def public_key_b64(priv) -> str:
    """Return compressed SPKI public key as base64 (matches what dashboard shows)."""
    from cryptography.hazmat.primitives import serialization
    pub = priv.public_key()
    spki = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(spki).decode()


def http_post(path, body, headers=None):
    h = {"Content-Type": "application/json", "User-Agent": "BizBot/1.0"}
    if headers: h.update(headers)
    req = urllib.request.Request(f"{API}{path}", data=json.dumps(body).encode(), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def http_get(path, headers=None):
    h = {"User-Agent": "BizBot/1.0", "Accept": "application/json"}
    if headers: h.update(headers)
    req = urllib.request.Request(f"{API}{path}", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def get_token(priv):
    """Mint acp-auth JWT. Caches to /tmp/acp_token.json with timestamp."""
    if os.path.exists(TOKEN_FILE):
        try:
            cached = json.load(open(TOKEN_FILE))
            if cached.get("expires_at", 0) > time.time() + 60:
                return cached["token"], cached.get("wallet")
        except Exception:
            pass

    ts = int(time.time() * 1000)
    msg = f"acp-auth:{ts}".encode()
    sig = sign_message(priv, msg)
    sig_b64 = base64.b64encode(sig).decode()

    body = {
        "walletAddress": WALLET,
        "signature": sig_b64,
        "message": msg.decode(),
        "chainId": 8453,
    }
    status, resp = http_post("/auth/agent", body)
    if status in (200, 201) and (resp.get("token") or resp.get("jwt") or resp.get("accessToken")):
        token = resp.get("token") or resp.get("jwt") or resp.get("accessToken")
        cached = {"token": token, "wallet": WALLET, "expires_at": time.time() + 3500}
        json.dump(cached, open(TOKEN_FILE, "w"))
        _log(f"auth OK token={token[:20]}...")
        return token, WALLET
    _log(f"auth FAIL status={status} resp={json.dumps(resp)[:200]}")
    sys.exit(f"Auth failed: {status} {resp}")


def cmd_auth():
    priv = load_key()
    pub = public_key_b64(priv)
    print(f"Wallet: {WALLET}")
    print(f"Pubkey: {pub[:50]}...")
    token, wallet = get_token(priv)
    print(f"✓ Auth OK")
    print(f"Token: {token[:30]}...")


def cmd_browse(q="code"):
    code, data = http_get(f"/agents/search?query={q}&topK=20", headers={"Origin": "https://app.virtuals.io"})
    if code != 200:
        sys.exit(f"Search failed: {code} {data}")
    count = 0
    for a in data.get("data", []):
        for c in a.get("chains", []):
            if c.get("acpV2AgentId") and c.get("active"):
                for o in a.get("offerings", [])[:2]:
                    print(f"  {a['name'][:25]:<25} | ${o['priceValue']:<6} | {o['name'][:35]:<35} | v2Id={c['acpV2AgentId']} | offeringId={o['id']}")
                    count += 1
                break
    print(f"\n{count} active offerings")


def cmd_test_job():
    """Smoke test: claim Rai AI quick_code_review ($0.05)."""
    priv = load_key()
    token, wallet = get_token(priv)

    # Rai AI quick_code_review: v2Id=17947, offering id 019d738d-b625-7ec0-8ef1-013a91a520e9
    # Per subagent research Jul 28 2026
    AGENT_ID = 17947
    OFFERING_ID = "019d738d-b625-7ec0-8ef1-013a91a520e9"
    JOB_ID = "70386"  # example job from research

    # Try to get job details
    code, job = http_get(f"/jobs/{JOB_ID}", headers={"Authorization": f"Bearer {token}"})
    print(f"GET /jobs/{JOB_ID}: {code}")
    if code == 200:
        print(json.dumps(job, indent=2)[:800])
    else:
        print(f"  {job}")
    _log(f"test_job: job {JOB_ID} status={code}")


def cmd_balance():
    """Check USDC on Base for agent wallet."""
    USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    DATA = "0x70a08231" + WALLET[2:].rjust(64, "0")
    body = {"jsonrpc": "2.0", "method": "eth_call",
            "params": [{"to": USDC, "data": DATA}, "latest"], "id": 1}
    req = urllib.request.Request(
        "https://mainnet.base.org",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        result = json.loads(r.read())
    wei = int(result["result"], 16)
    usdc = wei / 1e6
    print(f"Wallet: {WALLET}")
    print(f"USDC:   {usdc:.6f}")
    _log(f"balance_check: {usdc:.6f} USDC")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "auth"
    {"auth": cmd_auth, "browse": cmd_browse, "test-job": cmd_test_job, "balance": cmd_balance}[cmd]()