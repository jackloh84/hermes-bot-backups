#!/usr/bin/env python3
"""Background self-probe loop - keeps minia2a activity high.
Probes all endpoints every 4 hours. NOTE (Aug 5 2026): since service v2.3.0 the
paid endpoints return HTTP 402 (x402 paywall) to probes without X-PAYMENT — that
is EXPECTED (endpoint alive + monetized), counted as "gated", NOT a failure.
"""
import urllib.request, urllib.error, json, time, os
from pathlib import Path

ENDPOINT = "https://api.kachangsia.com/api"
LOG = Path("/home/ubuntu/.hermes/profiles/bot4/state/self_probe_loop.log")

PROBES = [
    {"action": "wallet-scan", "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"},
    {"action": "swap-quote"},
    {"action": "polymarket-odds", "slug": "will-bitcoin-hit-100k-by-2027"},
    {"action": "polymarket-list"},
    {"action": "address-validate", "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"},
    {"action": "token-info", "contract": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"},
    {"action": "contract-risk", "contract": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"},
    {"action": "nft-floor", "collection": "based-punks"},
    {"action": "echo", "msg": "loop-probe"},
]

def probe():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    ok = 0
    gate = 0
    for p in PROBES:
        try:
            req = urllib.request.Request(ENDPOINT, data=json.dumps(p).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "Jack-SelfProbeLoop/2.1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = json.loads(r.read())
                ok += 1
        except urllib.error.HTTPError as e:
            # 402 = x402 paywall active (endpoint alive + monetized since v2.3.0,
            # Aug 4 2026). Count as gate, not failure — probes without X-PAYMENT
            # legitimately get 402 on paid actions.
            if e.code == 402:
                gate += 1
            else:
                with open(LOG, "a") as f:
                    f.write(f"[{ts}] FAIL {p.get('action')}: HTTP {e.code}\n")
        except Exception as e:
            with open(LOG, "a") as f:
                f.write(f"[{ts}] FAIL {p.get('action')}: {e}\n")
        time.sleep(0.3)
    line = f"[{ts}] Probed {ok}/{len(PROBES)} endpoints OK ({gate} gated by x402 paywall)\n"
    with open(LOG, "a") as f:
        f.write(line)
    print(line.strip())

if __name__ == "__main__":
    probe()