#!/usr/bin/env python3
"""hl_withdraw.py — withdraw USDC from Hyperliquid to the hot wallet (Arbitrum).

Free (signed API call, no gas on our side). Moves USDC off the exchange into the
hot wallet on Arbitrum. The subsequent Arbitrum->Base bridge is a separate step
that needs Arbitrum gas.

Run: /home/ubuntu/venv/bin/python3 hl_withdraw.py
"""
import json, sys, time, urllib.request

HOT = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
HL_API = "https://api.hyperliquid.xyz"


def load_env():
    env = {}
    for f in ["/home/ubuntu/.hermes/.env", "/home/ubuntu/.hermes/profiles/bot4/.env"]:
        if __import__("os").path.exists(f):
            for line in open(f):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")


    return env


def hl_balance(addr):
    from hyperliquid.info import Info
    info = Info(HL_API, skip_ws=True)
    spot = info.spot_user_state(addr)
    bal = sum(float(b.get("total", 0)) for b in spot.get("balances", [])
              if b.get("coin") == "USDC")
    return bal


def main():
    env = load_env()
    pk = env.get("WALLET_PK")
    if not pk:
        print("FATAL: WALLET_PK not found")
        sys.exit(1)
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    acct = Account.from_key(pk)
    assert acct.address.lower() == HOT.lower(), f"key derives {acct.address}"

    bal = hl_balance(acct.address)
    print(f"HL balance before: ${bal:.4f}")
    if bal <= 0:
        print("Nothing to withdraw — balance is 0.")
        return

    amount = round(bal - 0.01, 2)  # leave $0.01 margin to avoid dust/rounding rejections
    if amount <= 0:
        amount = round(bal, 2)
    print(f"Withdrawing ${amount:.2f} USDC -> {HOT} (Arbitrum)")

    exchange = Exchange(acct, base_url="https://api.hyperliquid.xyz")
    try:
        result = exchange.withdraw_from_bridge(amount, HOT)
        print(f"Withdraw response: {json.dumps(result)[:300]}")
    except Exception as e:
        print(f"Withdraw ERROR: {type(e).__name__}: {str(e)[:300]}")
        sys.exit(1)

    time.sleep(15)
    bal2 = hl_balance(acct.address)
    print(f"HL balance after:  ${bal2:.4f}")
    print("DONE — USDC should now be on Arbitrum in the hot wallet.")


if __name__ == "__main__":
    main()
