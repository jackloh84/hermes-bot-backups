#!/usr/bin/env python3
"""Limitless profit bank — grow trading wallet to +$100 profit, then bank $100 to main.

Jack's rule (Aug 3 2026): start trading on the topped-up money; when the hot wallet
grows by an extra $100 (starting_balance + 100), transfer exactly $100 USDC to main
wallet 0xf52af41e... and keep the rest trading. Silent watchdog: prints only when
a transfer happens.
"""
import os, json, time, urllib.request
from datetime import datetime, timezone
from web3 import Web3
from eth_account import Account

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
HOT = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
MAIN = "0xf52af41e893c1f230a3db3bd07cd8417b2277e5c"
STATE_FILE = "/home/ubuntu/.hermes/profiles/bot4/state/limitless_profit_bank.json"
TARGET_PROFIT = 100.00   # transfer $100 to main after +$100 profit
RPC = "https://mainnet.base.org"
HD = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


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


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode(), headers=HD)
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def usdc_bal(addr):
    return int(rpc("eth_call", [{"to": USDC, "data": f"0x70a08231000000000000000000000000{addr[2:].lower()}"}, "latest"])["result"], 16) / 1e6


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {"start_balance": None, "banked": 0, "last_bank_ts": None, "last_balance": None}


def main():
    env = load_env()
    acct = Account.from_key(env["WALLET_PK"])
    assert acct.address.lower() == HOT.lower(), f"WALLET_PK derives {acct.address}, expected {HOT}"
    state = load_state()

    bal = usdc_bal(HOT)
    if state.get("start_balance") is None:
        state["start_balance"] = bal
        json.dump(state, open(STATE_FILE, "w"), indent=2)
        print(f"[profit-bank] start_balance set to ${bal:.2f} (target bank: ${bal + TARGET_PROFIT:.2f})")
        return

    start = state["start_balance"]
    target = start + TARGET_PROFIT
    state["last_balance"] = bal
    json.dump(state, open(STATE_FILE, "w"), indent=2)

    if bal < target:
        # silent — still growing
        return

    # transfer exactly $100 USDC to main, keep the rest trading
    w3 = Web3(Web3.HTTPProvider(RPC))
    w3.middleware_onion.clear()
    abi = [{"name": "transfer", "type": "function",
            "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
            "outputs": [{"name": "", "type": "bool"}]}]
    c = w3.eth.contract(address=Web3.to_checksum_address(USDC), abi=abi)
    amount = int(TARGET_PROFIT * 1e6)
    nonce = w3.eth.get_transaction_count(acct.address)
    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    tx = c.functions.transfer(Web3.to_checksum_address(MAIN), amount).build_transaction({
        "from": acct.address, "nonce": nonce, "gas": 60000,
        "maxFeePerGas": int(base_fee * 2), "maxPriorityFeePerGas": 0, "chainId": 8453,
    })
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    # wait for receipt
    rcpt = None
    for _ in range(30):
        try:
            rcpt = w3.eth.get_transaction_receipt(h)
            if rcpt:
                break
        except Exception:
            pass
        time.sleep(2)
    state["banked"] = state.get("banked", 0) + TARGET_PROFIT
    state["last_bank_ts"] = datetime.now(timezone.utc).isoformat()
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    print(f"💰 PROFIT BANKED: ${TARGET_PROFIT:.2f} USDC → main wallet")
    print(f"   tx: {h.hex()} block: {rcpt['blockNumber'] if rcpt else 'pending'}")
    print(f"   remaining hot: ${usdc_bal(HOT):.2f} (kept trading)")


if __name__ == "__main__":
    main()
