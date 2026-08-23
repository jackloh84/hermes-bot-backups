#!/usr/bin/env python3
"""
morpho_balance.py — weekly check of Jack's Morpho position (Gauntlet USDC Prime).

Reads the vault share balance, converts to USDC value, compares to last check,
and prints a short report. Empty stdout = silent (nothing sent).

State file: ~/.hermes/profiles/bot4/state/morpho_position.json
"""
import json, os, sys, time

VAULT = "0xeE8F4eC5672F09119b96Ab6fB59C27E1b7e44b61"  # Gauntlet USDC Prime (Base)
HOT   = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
STATE = "/home/ubuntu/.hermes/profiles/bot4/state/morpho_position.json"
RPCS  = ["https://base-rpc.publicnode.com", "https://base.drpc.org", "https://1rpc.io/base"]


def rpc_call(rpc_url, to, data):
    import urllib.request
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(rpc_url, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    })
    return json.loads(urllib.request.urlopen(req, timeout=20).read())["result"]


def balance_of(rpc_url, token, addr):
    data = "0x70a08231" + addr[2:].lower().rjust(64, "0")
    return int(rpc_call(rpc_url, token, data), 16)


def convert_to_assets(rpc_url, vault, shares):
    from eth_abi import encode
    data = "0x6e553f65" + encode(['uint256'], [shares]).hex()  # placeholder wrong sig
    return None


def main():
    shares = None
    last_err = None
    for rpc in RPCS:
        try:
            shares = balance_of(rpc, VAULT, HOT)
            break
        except Exception as e:
            last_err = e
    if shares is None:
        print(f"⚠️ Morpho check failed: {last_err}")
        return

    # convertToAssets(uint256) selector = 0x07a2d13a
    assets = None
    for rpc in RPCS:
        try:
            data = "0x07a2d13a" + format(shares, '064x')
            assets = int(rpc_call(rpc, VAULT, data), 16)
            break
        except Exception as e:
            last_err = e

    if assets is None:
        print(f"⚠️ Morpho value read failed: {last_err} (shares={shares/1e18:.4f})")
        return

    usd = assets / 1e6
    prev = {}
    if os.path.exists(STATE):
        try:
            prev = json.load(open(STATE))
        except Exception:
            prev = {}
    prev_usd = prev.get("usd", usd)
    change = usd - prev_usd
    prev_ts = prev.get("ts", 0)
    days = (time.time() - prev_ts) / 86400 if prev_ts else 0

    # save state
    json.dump({"usd": usd, "shares": shares, "ts": time.time()}, open(STATE, "w"))

    sign = "+" if change >= 0 else ""
    delta = f" ({sign}{change:.4f} USDC)" if prev_ts else " (first check)"
    print(f"💰 Morpho balance: ${usd:.4f} USDC{delta} — {shares/1e18:.6f} gtUSDCp shares")


if __name__ == "__main__":
    main()
