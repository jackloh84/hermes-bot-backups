#!/usr/bin/env python3
"""Re-register all Jack's minia2a services with the live tunnel URL.

Each service gets a NARROW, trend-matching name (per agent-marketplace-audit pitfall #22)
and points to the current live cloudflared tunnel URL.
"""
import json
import urllib.request
import urllib.error
import time

LIVE_TUNNEL = "https://alfred-tyler-captured-optimize.trycloudflare.com/api"
WALLET = "0xf52af41e893c1f230a3db3bd07cd8417b2277e5c"
AGENT = "Jack Loh @jacklohai"

# Service definitions: (name, description, category, priceCents)
# Names mirror trending search terms from the leaderboard (per pitfall #22)
SERVICES = [
    (
        "Polymarket Odds Live",
        "Live Polymarket prediction-market odds by slug. Returns yes/no %, volume, liquidity, 24h change. Example: POST {\"action\":\"polymarket-odds\",\"slug\":\"bitcoin-100k-2026\"}. $0.01/call.",
        "data",
        1,
    ),
    (
        "Web Scraper x402",
        "Fetch any public URL and return cleaned text + metadata. POST {\"action\":\"web-fetch\",\"url\":\"https://...\"}. Handles JS-rendered pages via fallback. $0.005/call.",
        "tools",
        1,
    ),
    (
        "Base Token Security Scanner",
        "Heuristic contract risk for any Base mainnet contract. POST {\"action\":\"contract-risk\",\"address\":\"0x...\"}. Returns verified status, proxy detection, source-code flags. $0.005/call.",
        "tools",
        1,
    ),
    (
        "On-Chain Wallet Profile",
        "Multi-chain wallet balance + USDC + ETH for any address. POST {\"action\":\"wallet-scan\",\"address\":\"0x...\"}. Returns Base + mainnet snapshot. $0.005/call.",
        "tools",
        1,
    ),
    (
        "Base USDC Swap Quote",
        "Indicative USDC->ETH swap rate on Base via on-chain quotes. POST {\"action\":\"swap-quote\",\"amountUsdc\":100}. Returns expected ETH + current base block. $0.005/call.",
        "tools",
        1,
    ),
    (
        "Multi-Chain Gas Price",
        "Current gas price on Base + Ethereum mainnet. Returns gwei + estimated tx cost in USD. POST {\"action\":\"gas\"}. $0.005/call.",
        "tools",
        1,
    ),
    (
        "Token Holder Lookup",
        "Top 10 ERC-20 holders on Base for any token. POST {\"action\":\"token-holders\",\"address\":\"0x...\"}. Sample recent Transfer events. $0.005/call.",
        "tools",
        1,
    ),
]

url = "https://www.minia2a.uk/api/register"
results = []
for name, desc, cat, price in SERVICES:
    payload = {
        "name": name,
        "endpoint": LIVE_TUNNEL,
        "priceCents": price,
        "wallet": WALLET,
        "desc": desc,
        "category": cat,
        "agentName": AGENT,
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            results.append({"name": name, "ok": True, "status": resp.status, "body": body[:200]})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        results.append({"name": name, "ok": False, "status": e.code, "body": body[:300]})
    except Exception as e:
        results.append({"name": name, "ok": False, "status": 0, "body": str(e)})
    time.sleep(0.5)

print(json.dumps(results, indent=2))
print()
ok = sum(1 for r in results if r["ok"])
print(f"REGISTERED OK: {ok}/{len(results)}")