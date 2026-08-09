#!/usr/bin/env python3
"""Self-probe loop to seed minia2a marketplace activity.

Burns credits on Jack's free wallet (0xa1fc721e...) to drive calls on /x402/*
endpoints. Hits Jack's OWN services too (via direct endpoint with wallet param).
"""
import json, time, urllib.request, os

WALLET = "0xa1fc721e2f8fc0374481d373732fd5697b2791d4"

# Real services to spend credits on (drives their trialCount + calls)
ENDPOINTS = [
    ("/x402/gas", {}),
    ("/x402/wallet", {}),
    ("/x402/wallet-intel", {}),
    ("/x402/polymarket", {}),
    ("/x402/polymarket-scan", {}),
    ("/x402/token-security", {}),
    ("/x402/token-search", {}),
    ("/x402/swap-safety", {}),
    ("/x402/gas-time", {}),
    ("/x402/dex-price", {}),
    ("/x402/rpc", {}),
    ("/x402/fetch", {"url": "https://api.kachangsia.com/openapi.json"}),
    ("/x402/web-scrape", {"url": "https://minia2a.uk/AGENTS.md"}),
    ("/x402/find", {"query": "x402 agent wallet"}),
    ("/x402/summarize", {"text": "ACP is the Agent Commerce Protocol for AI agents on Base L2."}),
    ("/x402/token-search", {"query": "USDC"}),
    ("/x402/markdown", {"text": "# x402\nPay per call in USDC on Base."}),
    ("/x402/hash", {"algo": "sha256", "text": "bizbot"}),
    ("/x402/keyword-extract", {"text": "agent earning on x402 USDC"}) if False else ("/x402/keywords", {"text": "agent x402 USDC earning"}),
    ("/x402/json-validate", {"json": '{"a":1,"b":2}'}),
    ("/x402/regex-explain", {"regex": "0x[a-fA-F0-9]{40}"}),
]

# Also call Jack's OWN endpoints directly (parameter doesn't trigger credit tracking but seens external calls)
JACK_DIRECT = [
    ("https://api.kachangsia.com/api", {"action": "wallet-scan", "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"}),
    ("https://api.kachangsia.com/api", {"action": "token-info", "contract": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"}),
    ("https://api.kachangsia.com/api", {"action": "contract-risk", "contract": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"}),
    ("https://api.kachangsia.com/api", {"action": "polymarket-list"}),
]


def hit_minia2a(ep, params):
    url = f"https://minia2a.uk{ep}?wallet={WALLET}"
    if params:
        url += "&" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BizBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:100]}


def hit_jack(url, body):
    try:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "BizBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:100]}


import urllib.parse

print("[self-probe] starting credit burn + Jack direct hits")
ok_minia2a = 0
ok_jack = 0
for ep, params in ENDPOINTS:
    r = hit_minia2a(ep, params)
    ok = r.get("ok") is True
    if ok: ok_minia2a += 1
    print(f"  minia2a {ep:<30} : {'✓' if ok else '✗'}")
    time.sleep(0.2)

for url, body in JACK_DIRECT:
    r = hit_jack(url, body)
    has_data = "address" in r or "markets" in r or "name" in r or "ok" in r
    if has_data: ok_jack += 1
    print(f"  jack    {body.get('action','?'):<20} : {'✓' if has_data else '✗'}")
    time.sleep(0.2)

# Final credit balance
bal = hit_minia2a("/api/v1/credits", {})
print(f"\n[result] minia2a OK: {ok_minia2a}/{len(ENDPOINTS)} | jack OK: {ok_jack}/{len(JACK_DIRECT)} | credits remaining: {bal.get('credits', '?')}")