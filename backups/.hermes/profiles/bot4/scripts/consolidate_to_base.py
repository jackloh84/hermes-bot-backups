#!/usr/bin/env python3
"""
consolidate_to_base.py — bridge hot wallet USDC from Arbitrum -> Base.

Purpose: consolidate the ~$18.96 USDC sitting on Arbitrum back to the Base
hot wallet so everything is in ONE earning wallet, ready to park in a lending
lane (Morpho/Moonwell/Aave on Base).

Modes:
  python3 consolidate_to_base.py            # DRY RUN (quotes only, signs nothing)
  python3 consolidate_to_base.py --execute  # sign + broadcast the bridge
  python3 consolidate_to_base.py --amount N # override amount (default = full Arb balance)

Uses WALLET_PK from ~/.hermes/.env (hot wallet 0x57E33b...).
Reverse of hl_fund.py (which bridged Base -> Arbitrum).
"""
import json, os, sys, time, urllib.request

HOT          = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
BASE_USDC    = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ARB_USDC     = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
ARB_CHAIN    = 42161
BASE_CHAIN   = 8453
BASE_RPC     = "https://base.drpc.org"
ARB_RPC      = "https://arb-pokt.nodies.app"   # arb1.arbitrum.io 403s from this VPS (Aug 2026)
RELAY_URL    = "https://api.relay.link/quote"

DRY = "--execute" not in sys.argv
AMOUNT_OVERRIDE = None
if "--amount" in sys.argv:
    AMOUNT_OVERRIDE = float(sys.argv[sys.argv.index("--amount") + 1])


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


def rpc(rpc_url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(rpc_url, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
    })
    return json.loads(urllib.request.urlopen(req, timeout=20).read())["result"]


def balance_of(rpc_url, token, addr):
    data = "0x70a08231" + addr[2:].lower().rjust(64, "0")
    return int(rpc(rpc_url, "eth_call", [{"to": token, "data": data}, "latest"]), 16) / 1e6


def eth_balance(rpc_url, addr):
    return int(rpc(rpc_url, "eth_getBalance", [addr, "latest"]), 16) / 1e18


def relay_quote(origin_chain, origin_cur, dest_chain, dest_cur, amount, user):
    body = json.dumps({
        "user": user,
        "originChainId": origin_chain,
        "originCurrency": origin_cur,
        "destinationChainId": dest_chain,
        "destinationCurrency": dest_cur,
        "amount": str(amount),
        "tradeType": "EXACT_INPUT",
    }).encode()
    req = urllib.request.Request(RELAY_URL, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def main():
    print("=" * 60)
    print("CONSOLIDATE ARB -> BASE — " + ("DRY RUN (nothing signed)" if DRY else "EXECUTE MODE"))
    print("=" * 60)
    env = load_env()
    pk = env.get("WALLET_PK")
    if not pk:
        print("FATAL: WALLET_PK not found"); sys.exit(1)
    from eth_account import Account
    acct = Account.from_key(pk)
    assert acct.address.lower() == HOT.lower(), f"key derives {acct.address}"
    print(f"Wallet: {acct.address}")

    arb_usdc = balance_of(ARB_RPC, ARB_USDC, HOT)
    arb_eth  = eth_balance(ARB_RPC, HOT)
    print(f"\nArb USDC : ${arb_usdc:.4f}")
    print(f"Arb ETH  : {arb_eth:.6f} (for gas)")

    amount = arb_usdc if AMOUNT_OVERRIDE is None else AMOUNT_OVERRIDE
    if amount <= 0:
        print("Nothing to bridge — Arbitrum USDC is 0."); return
    usdc_amt = int(amount * 1e6)
    print(f"Bridging : ${amount:.4f} USDC  Arb -> Base")

    q = relay_quote(ARB_CHAIN, ARB_USDC, BASE_CHAIN, BASE_USDC, usdc_amt, HOT)
    if "steps" not in q:
        print(f"Relay quote error: {json.dumps(q)[:400]}"); return
    print(f"\nRelay quote: {len(q.get('steps', []))} steps")
    for i, s in enumerate(q.get("steps", [])):
        for it in s.get("items", []):
            d = it.get("data", {})
            print(f"  step{i} {s.get('id')}: to={d.get('to','')} gas={d.get('gas')}")
    fees = q.get("fees", {})
    print(f"  fees (relayer usd): ~${fees.get('relayer',{}).get('amountUsd','?')}")

    if DRY:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE — nothing signed/broadcast.")
        print("Execute: python3 consolidate_to_base.py --execute")
        print("=" * 60)
        return

    # ---- execute ----
    print("\n--- EXECUTING ---")
    from web3 import Web3
    w3a = Web3(Web3.HTTPProvider(ARB_RPC))

    def send_tx(w3, tx):
        tx["from"] = acct.address
        tx["nonce"] = w3.eth.get_transaction_count(acct.address)
        for k in ("value", "gas", "maxFeePerGas", "maxPriorityFeePerGas", "gasPrice"):
            if k in tx and isinstance(tx[k], str):
                tx[k] = int(tx[k])
        if tx.get("to") and isinstance(tx["to"], str):
            tx["to"] = Web3.to_checksum_address(tx["to"])
        if "maxFeePerGas" not in tx and "gasPrice" not in tx:
            tx["gasPrice"] = w3.eth.gas_price
        if "gas" not in tx:
            tx["gas"] = w3.eth.estimate_gas(tx)
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        print(f"  tx {h.hex()} ... waiting")
        deadline = time.time() + 180
        rec = None
        while time.time() < deadline:
            try:
                rec = w3.eth.get_transaction_receipt(h)
                if rec is not None: break
            except Exception: pass
            time.sleep(5)
        if rec is None:
            print(f"  WARN: no receipt yet for {h.hex()}")
        else:
            print(f"  confirmed {h.hex()[:20]}... status={rec.get('status')}")
        return h

    for s in q.get("steps", []):
        for it in s.get("items", []):
            d = it.get("data", {})
            if d.get("to"):
                print(f"  sending step '{s.get('id')}' ...")
                send_tx(w3a, d)

    print("\n  waiting 60s for bridge finality...")
    time.sleep(60)
    print(f"\n--- POST-BRIDGE BALANCES ---")
    print(f"Arb USDC : ${balance_of(ARB_RPC, ARB_USDC, HOT):.4f}")
    print(f"Base USDC: ${balance_of(BASE_RPC, BASE_USDC, HOT):.4f}")
    print("DONE")


if __name__ == "__main__":
    main()
