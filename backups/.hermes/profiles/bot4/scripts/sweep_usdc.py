#!/usr/bin/env python3
"""Sweep USDC from BountyBook wallet to Jack's destination wallet.

Usage:
    python3 sweep_usdc.py           # sweep all to JACK_WALLET (with 0.10 USDC buffer)
    python3 sweep_usdc.py --dry-run # show what would happen
    python3 sweep_usdc.py --amount 5.0  # send specific amount

Jack's destination wallet (from Telegram 2026-07-28):
    0xf52af41e893c1f230a3db3bd07cd8417b2277e5c
"""
import json, os, sys, time, urllib.request, subprocess

WALLET = os.environ.get("BOUNTYBOOK_WALLET_ADDRESS", "0xD2965001942B7BE86143510dB9945875301e639b")
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
JACK_WALLET = os.environ.get("JACK_WALLET", "0xf52af41e893c1f230a3db3bd07cd8417b2277e5c")

BALANCEOF = "0x70a08231000000000000000000000000" + WALLET[2:]


def http_post(url, body, headers=None):
    h = {"Content-Type": "application/json", "User-Agent": "BizBot/1.0"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get_balance_usdc():
    r = http_post("https://mainnet.base.org",
                  {"jsonrpc": "2.0", "method": "eth_call",
                   "params": [{"to": USDC_BASE, "data": BALANCEOF}, "latest"], "id": 1})
    return int(r["result"], 16) / 1e6


def get_eth_balance():
    r = http_post("https://mainnet.base.org",
                  {"jsonrpc": "2.0", "method": "eth_getBalance",
                   "params": [WALLET, "latest"], "id": 1})
    return int(r["result"], 16) / 1e18


def send_usdc(to_addr, amount_usdc):
    pk = os.environ.get("BOUNTYBOOK_PRIVATE_KEY")
    if not pk:
        return {"error": "BOUNTYBOOK_PRIVATE_KEY not set"}

    amount_raw = int(amount_usdc * 1e6)
    to_clean = to_addr if to_addr.startswith("0x") else "0x" + to_addr

    js_code = f'''
    const {{ createWalletClient, http, encodeFunctionData }} = await import("viem");
    const {{ base }} = await import("viem/chains");
    const {{ privateKeyToAccount }} = await import("viem/accounts");
    const account = privateKeyToAccount("{pk}");
    const client = createWalletClient({{ account, chain: base, transport: http() }});

    const data = encodeFunctionData({{
      abi: [{{ name: "transfer", type: "function", stateMutability: "nonpayable",
              inputs: [{{ name: "to", type: "address" }}, {{ name: "amount", type: "uint256" }}],
              outputs: [{{ name: "", type: "bool" }}] }}],
      functionName: "transfer",
      args: ["{to_clean}", {amount_raw}n],
    }});

    const hash = await client.sendTransaction({{
      to: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      data,
    }});
    console.log(hash);
    '''
    r = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, timeout=60,
        cwd="/home/ubuntu/.hermes/profiles/bot4/scripts",
    )
    if r.returncode != 0:
        return {"error": r.stderr.strip(), "stdout": r.stdout}
    return {"tx_hash": r.stdout.strip()}


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    explicit_amount = None
    if "--amount" in args:
        idx = args.index("--amount")
        explicit_amount = float(args[idx + 1])

    to = JACK_WALLET
    usdc_bal = get_balance_usdc()
    eth_bal = get_eth_balance()
    print(f"From: {WALLET}")
    print(f"To:   {to}")
    print(f"USDC balance: {usdc_bal:.6f}")
    print(f"ETH balance:  {eth_bal:.6f} (gas)")

    if explicit_amount is not None:
        amount = explicit_amount
    else:
        amount = max(0, usdc_bal - 0.10)  # leave 0.10 USDC buffer

    if amount <= 0:
        print("\nNothing to sweep.")
        sys.exit(0)

    if amount > usdc_bal:
        print(f"\nInsufficient USDC: trying {amount}, have {usdc_bal}")
        sys.exit(1)

    if eth_bal < 0.001:
        print(f"\nWARNING: low ETH for gas ({eth_bal:.6f})")

    print(f"\nWill send: {amount:.6f} USDC")

    if dry_run:
        print("[dry-run] exiting without sending")
        sys.exit(0)

    result = send_usdc(to, amount)
    print(json.dumps(result, indent=2))