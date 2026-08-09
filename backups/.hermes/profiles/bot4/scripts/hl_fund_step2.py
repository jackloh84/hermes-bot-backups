#!/usr/bin/env python3
"""hl_fund_step2.py — bridge ETH Base->Arb then deposit USDC->HL (resume path)."""
import json, os, sys, time, urllib.request

HOT = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
ARB_USDC = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
HL_BRIDGE = "0x2df1c51e09aecf9cacb7bc98cb1742757f163df7"
BASE_RPC = "https://base.drpc.org"
ARB_RPC = "https://arb1.arbitrum.io/rpc"
RELAY_URL = "https://api.relay.link/quote"
HL_API = "https://api.hyperliquid.xyz/info"
ETH_AMT = 0.0002  # ~$0.38 for Arb gas

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

def rpc_call(rpc, method, params):
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req = urllib.request.Request(rpc, data=body, headers={
        "Content-Type":"application/json",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

def eth_balance(rpc, addr):
    return int(rpc_call(rpc, "eth_getBalance", [addr, "latest"])["result"], 16) / 1e18

def wait_receipt(w3, h, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rec = w3.eth.get_transaction_receipt(h)
            if rec is not None:
                return rec
        except Exception:
            pass
        time.sleep(6)
    return None

env = load_env()
from eth_account import Account
from web3 import Web3
acct = Account.from_key(env["WALLET_PK"])
assert acct.address.lower() == HOT.lower()
w3b = Web3(Web3.HTTPProvider(BASE_RPC))
w3a = Web3(Web3.HTTPProvider(ARB_RPC))

print("Base ETH:", eth_balance(BASE_RPC, HOT))
print("Arb ETH :", eth_balance(ARB_RPC, HOT))

# --- step 1: bridge ETH Base->Arb via Relay (skip if already funded) ---
if eth_balance(ARB_RPC, HOT) >= 0.00002:
    print("Arb ETH already funded — skipping ETH bridge")
else:
    body = json.dumps({
        "user": HOT,
        "originChainId": 8453,
        "originCurrency": "0x" + "0" * 40,
        "destinationChainId": 42161,
        "destinationCurrency": "0x" + "0" * 40,
        "amount": str(int(ETH_AMT * 1e18)),
        "tradeType": "EXACT_INPUT",
    }).encode()
    req = urllib.request.Request(RELAY_URL, data=body, headers={"Content-Type": "application/json"})
    q = json.loads(urllib.request.urlopen(req, timeout=25).read())
    print("ETH bridge steps:", len(q.get("steps", [])))
    for s in q.get("steps", []):
        for it in s.get("items", []):
            d = it.get("data", {})
            for k in ("value", "gas", "maxFeePerGas", "maxPriorityFeePerGas"):
                if k in d and isinstance(d[k], str):
                    d[k] = int(d[k])
            if d.get("to"):
                d["to"] = Web3.to_checksum_address(d["to"])
            d["from"] = acct.address
            d["nonce"] = w3b.eth.get_transaction_count(acct.address)
            if "maxFeePerGas" not in d:
                d["gasPrice"] = w3b.eth.gas_price
            signed = acct.sign_transaction(d)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            h = w3b.eth.send_raw_transaction(raw)
            print("ETH bridge tx:", h.hex())
            rec = wait_receipt(w3b, h)
            if rec is None:
                print("WARN: ETH bridge not confirmed, nonce might be stuck")
            else:
                print("ETH bridge mined, status:", rec.get("status"))

print("waiting 45s for bridge credit...")
time.sleep(45)
print("Arb ETH after bridge:", eth_balance(ARB_RPC, HOT))

# --- step 2: deposit USDC on Arbitrum -> HL bridge ---
arb_eth = eth_balance(ARB_RPC, HOT)
if arb_eth < 0.00002:
    print("FATAL: still no ETH on Arbitrum, cannot pay deposit gas")
    sys.exit(1)

usdc_abi = json.loads('[{"constant":true,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"to","type":"address"},{"name":"value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]')
usdc = w3a.eth.contract(address=Web3.to_checksum_address(ARB_USDC), abi=usdc_abi)
bal = usdc.functions.balanceOf(acct.address).call() / 1e6
print("Arb USDC balance:", bal)
tx = usdc.functions.transfer(Web3.to_checksum_address(HL_BRIDGE), int(bal * 1e6)).build_transaction({
    "from": acct.address,
    "nonce": w3a.eth.get_transaction_count(acct.address),
    "gasPrice": w3a.eth.gas_price,
})
tx["gas"] = 120000
signed = acct.sign_transaction(tx)
raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
h = w3a.eth.send_raw_transaction(raw)
print("HL deposit tx:", h.hex())
rec = wait_receipt(w3a, h)
print("deposit mined, status:", rec.get("status") if rec else "UNKNOWN")

print("waiting 60s for HL credit...")
time.sleep(60)
body = json.dumps({"type": "clearinghouseState", "user": acct.address}).encode()
req = urllib.request.Request(HL_API, data=body, headers={"Content-Type": "application/json"})
state = json.loads(urllib.request.urlopen(req, timeout=20).read())
print("HL USDC balance: $", float(state.get("marginSummary", {}).get("accountValue", 0)))
