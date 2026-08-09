#!/usr/bin/env python3
"""
hl_fund.py — Hyperliquid funding script for the hot wallet (REVIEW FIRST).

Flow (verified live Aug 9 2026):
  1. Bridge USDC  Base -> Arbitrum  (Relay API, approve + bridge)
  2. Bridge ETH   Base -> Arbitrum  (Relay API, for Arb gas)
  3. Deposit USDC on Arbitrum -> Hyperliquid bridge
     (simple ERC-20 transfer of USDC to HL bridge 0x2df1c51e..., credited to sender)

Modes:
  python3 hl_fund.py                  # DRY RUN: quotes + exact txs, signs NOTHING
  python3 hl_fund.py --execute        # actually signs + broadcasts (only after Jack OK)
  python3 hl_fund.py --amount 20      # override deposit amount (default $20)

Uses WALLET_PK from ~/.hermes/.env (same key as Gains lane).
"""
import json, os, sys, time, urllib.request

# ---------- config ----------
AMOUNT_USDC = 20.0            # default deposit amount
ETH_FOR_GAS  = 0.0002         # ~$0.38 ETH bridged for Arbitrum deposit gas (Base ETH is only $0.87)
HOT          = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
BASE_USDC    = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ARB_USDC     = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
HL_BRIDGE    = "0x2df1c51e09aecf9cacb7bc98cb1742757f163df7"  # HL bridge on Arbitrum (mainnet)
BASE_RPC     = "https://base.drpc.org"
ARB_RPC      = "https://arb1.arbitrum.io/rpc"
BASE_RPC_FALLBACKS = ["https://base-rpc.publicnode.com", "https://1rpc.io/base"]
RELAY_URL    = "https://api.relay.link/quote"
HL_API       = "https://api.hyperliquid.xyz/info"

DRY = "--execute" not in sys.argv
if "--amount" in sys.argv:
    AMOUNT_USDC = float(sys.argv[sys.argv.index("--amount") + 1])


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
    print("HYPERLIQUID FUNDING — " + ("DRY RUN (nothing signed)" if DRY else "EXECUTE MODE"))
    print("=" * 60)
    env = load_env()
    pk = env.get("WALLET_PK")
    if not pk:
        print("FATAL: WALLET_PK not found in env")
        sys.exit(1)

    from eth_account import Account
    acct = Account.from_key(pk)
    assert acct.address.lower() == HOT.lower(), f"key derives {acct.address}, expected {HOT}"
    print(f"Wallet     : {acct.address}")
    print(f"Deposit    : ${AMOUNT_USDC:.2f} USDC  (+ ~${ETH_FOR_GAS * 1900:.2f} ETH for gas)")

    # -------- current balances --------
    print("\n--- CURRENT BALANCES ---")
    print(f"Base USDC  : ${balance_of(BASE_RPC, BASE_USDC, HOT):.4f}")
    print(f"Base ETH   : {eth_balance(BASE_RPC, HOT):.6f}")
    print(f"Arb USDC   : ${balance_of(ARB_RPC, ARB_USDC, HOT):.4f}")
    print(f"Arb ETH    : {eth_balance(ARB_RPC, HOT):.6f}")

    usdc_amt = int(AMOUNT_USDC * 1e6)  # 6 decimals
    eth_amt = int(ETH_FOR_GAS * 1e18)  # 18 decimals

    # -------- step 1+2: relay quotes --------
    print("\n--- BRIDGE QUOTES (Relay) ---")
    q_usdc = relay_quote(8453, BASE_USDC, 42161, ARB_USDC, usdc_amt, HOT)
    print(f"USDC Base->Arb: {len(q_usdc.get('steps', []))} steps")
    for i, s in enumerate(q_usdc.get("steps", [])):
        for it in s.get("items", []):
            d = it.get("data", {})
            print(f"  step{i} tx: to={d.get('to','')[:20]}... from={d.get('from','')[:20]}...")
    fees = q_usdc.get("fees", {})
    print(f"  relay fees: {json.dumps(fees)[:200]}")

    q_eth = relay_quote(8453, "0x" + "0" * 40, 42161, "0x" + "0" * 40, eth_amt, HOT)
    print(f"ETH Base->Arb: {len(q_eth.get('steps', []))} steps (for Arb gas)")

    if DRY:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE — nothing was signed or broadcast.")
        print("Review the quotes above. To execute: python3 hl_fund.py --execute")
        print("=" * 60)
        return

    # -------- execute: sign relay bridge txs --------
    print("\n--- EXECUTING ---")
    from web3 import Web3
    w3b = Web3(Web3.HTTPProvider(BASE_RPC))
    w3a = Web3(Web3.HTTPProvider(ARB_RPC))

    def send_tx(w3, tx):
        tx["from"] = acct.address
        tx["nonce"] = w3.eth.get_transaction_count(acct.address)
        # Relay API returns numeric fields as strings; coerce to int
        for k in ("value", "gas", "maxFeePerGas", "maxPriorityFeePerGas", "gasPrice"):
            if k in tx and isinstance(tx[k], str):
                tx[k] = int(tx[k])
        # typed txs require checksummed to-address
        if tx.get("to") and isinstance(tx["to"], str):
            tx["to"] = Web3.to_checksum_address(tx["to"])
        # Relay txs already carry EIP-1559 gas fields (maxFeePerGas etc.)
        if "maxFeePerGas" not in tx and "gasPrice" not in tx:
            tx["gasPrice"] = w3.eth.gas_price
        if "gas" not in tx:
            tx["gas"] = w3.eth.estimate_gas(tx)
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        print(f"  tx {h.hex()} waiting")
        # poll receipt across multiple RPCs (public RPCs rate-limit)
        import time as _t
        deadline = _t.time() + 180
        rec = None
        while _t.time() < deadline:
            try:
                rec = w3.eth.get_transaction_receipt(h)
                if rec is not None:
                    break
            except Exception:
                pass
            _t.sleep(5)
        if rec is None:
            print(f"  WARN: receipt not confirmed on primary RPC, tx {h.hex()} may still mine")
        else:
            print(f"  confirmed {h.hex()[:20]}...")
        return h

    # 1. USDC approve -> relay
    for s in q_usdc.get("steps", []):
        for it in s.get("items", []):
            d = it.get("data", {})
            if d.get("to"):
                print(f"  sending {d.get('to')[:20]}...")
                send_tx(w3b, d)

    # 2. ETH bridge
    for s in q_eth.get("steps", []):
        for it in s.get("items", []):
            d = it.get("data", {})
            if d.get("to"):
                send_tx(w3b, d)

    print("\n  waiting 60s for bridge finality...")
    time.sleep(60)

    # 3. Deposit USDC on Arbitrum -> HL bridge (simple transfer)
    print("  depositing USDC on Arbitrum -> HL bridge...")
    usdc_contract = w3a.eth.contract(
        address=Web3.to_checksum_address(ARB_USDC),
        abi=json.loads('[{"constant":false,"inputs":[{"name":"to","type":"address"},{"name":"value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]'),
    )
    tx = usdc_contract.functions.transfer(
        Web3.to_checksum_address(HL_BRIDGE), usdc_amt
    ).build_transaction({
        "from": acct.address,
        "nonce": w3a.eth.get_transaction_count(acct.address),
        "gasPrice": w3a.eth.gas_price,
    })
    tx["gas"] = 120000
    signed = acct.sign_transaction(tx)
    h = w3a.eth.send_raw_transaction(signed.rawTransaction)
    print(f"  deposit tx {h.hex()[:20]}... waiting")
    w3a.eth.wait_for_transaction_receipt(h, timeout=180)
    print(f"  deposit confirmed {h.hex()[:20]}...")

    # 4. verify HL balance
    print("\n--- VERIFY HYPERLIQUID BALANCE ---")
    time.sleep(45)
    body = json.dumps({"type": "clearinghouseState", "user": acct.address}).encode()
    req = urllib.request.Request(HL_API, data=body, headers={"Content-Type": "application/json"})
    state = json.loads(urllib.request.urlopen(req, timeout=20).read())
    print(f"HL USDC balance: ${float(state.get('marginSummary', {}).get('accountValue', 0)):.2f}")
    print("DONE")


if __name__ == "__main__":
    main()
