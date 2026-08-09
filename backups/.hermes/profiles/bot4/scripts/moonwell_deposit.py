#!/usr/bin/env python3
"""Deposit USDC into Moonwell (Base) using the official prepare/supply flow.
3 txs: approve -> enter-market -> supply. Signs with HOT wallet, broadcasts sequentially."""
import json, sys, time, os
sys.path.insert(0, '/home/ubuntu')
from eth_account import Account
from web3 import Web3

RPC = "https://mainnet.base.org"
w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 30}))

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

def send_tx(acct, tx):
    nonce = w3.eth.get_transaction_count(acct.address)
    gas_price = w3.eth.gas_price
    base_tx = {
        "to": Web3.to_checksum_address(tx["to"]),
        "data": tx["data"],
        "value": int(tx.get("value", "0x0"), 16) if isinstance(tx.get("value"), str) and tx.get("value","").startswith("0x") else int(tx.get("value", 0)),
        "nonce": nonce,
        "chainId": 8453,
        "gasPrice": gas_price,
    }
    # estimate gas
    try:
        base_tx["gas"] = w3.eth.estimate_gas({"from": acct.address, "to": base_tx["to"], "data": base_tx["data"], "value": base_tx["value"]})
    except Exception as e:
        print("  gas estimate fallback:", str(e)[:100])
        base_tx["gas"] = 200000
    signed = acct.sign_transaction(base_tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  tx {tx_hash.hex()[:18]}... gas={base_tx['gas']}")
    # wait for receipt
    for _ in range(60):
        try:
            rcpt = w3.eth.get_transaction_receipt(tx_hash)
            if rcpt:
                status = rcpt.get("status")
                print(f"  receipt: status={status} block={rcpt.get('blockNumber')}")
                return status == 1
        except Exception:
            pass
        time.sleep(2)
    print("  timeout waiting receipt")
    return False

def main():
    env = load_env()
    acct = Account.from_key(env["WALLET_PK"])
    print("wallet:", acct.address)
    prep = json.load(open("/tmp/mwprep.json"))["data"]
    txs = prep["transactions"]
    print(f"txs to execute: {len(txs)}")
    for i, tx in enumerate(txs, 1):
        print(f"\n[{i}/{len(txs)}] {tx.get('step')} — {tx.get('description','')}")
        ok = send_tx(acct, tx)
        if not ok:
            print("FAILED at step", i)
            sys.exit(1)
        time.sleep(1)
    # verify mUSDC balance
    mUSDC = "0xEdc817A28E8B93B03976FBd4a3dDBc9f7D176c22"
    baldata = "0x70a08231" + acct.address.lower()[2:].rjust(64, "0")
    import urllib.request
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to": mUSDC, "data": baldata}, "latest"]}).encode(),
        headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"}, method="POST")
    res = json.loads(urllib.request.urlopen(req, timeout=20).read()).get("result")
    bal = int(res, 16) / 1e6 if res else 0
    print(f"\n✅ mUSDC balance: {bal:.4f} mUSDC (deposited $25 USDC)")

if __name__ == "__main__":
    main()
