#!/usr/bin/env python3
"""Auto-sweep cron: every 6h, check 0x57E33b USDC balance.
If > $1, sweep to 0xf52af41e + TG alert.

Source: ~/.hermes/profiles/bot4/scripts/auto_sweep.py
"""
import os, json, subprocess, urllib.request, time
from datetime import datetime, timezone

HOT_WALLET = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
MAIN_WALLET = "0xf52af41e893c1f230a3db3bd07cd8417b2277e5c"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
THRESHOLD_USDC = 1.00
STATE_FILE = "/home/ubuntu/.hermes/profiles/bot4/state/auto_sweep.json"
MIN_GAS_ETH = 0.0003  # need at least this much ETH to sweep


def get_usdc_balance(addr):
    req = urllib.request.Request("https://mainnet.base.org",
        data=json.dumps({"jsonrpc":"2.0","method":"eth_call","params":[
            {"to": USDC_BASE, "data": f"0x70a08231000000000000000000000000{addr[2:].lower()}"}, "latest"
        ],"id":1}).encode(),
        headers={"User-Agent":"Mozilla/5.0", "Content-Type":"application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=8).read())
    if "result" not in r:
        raise RuntimeError(f"RPC no result: {r}")
    return int(r["result"], 16) / 1e6


def get_eth_balance(addr):
    req = urllib.request.Request("https://mainnet.base.org",
        data=json.dumps({"jsonrpc":"2.0","method":"eth_getBalance","params":[addr,"latest"],"id":1}).encode(),
        headers={"User-Agent":"Mozilla/5.0", "Content-Type":"application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=8).read())
    if "result" not in r:
        raise RuntimeError(f"RPC no result: {r}")
    return int(r["result"], 16) / 1e18


def get_tg_token():
    p = "/home/ubuntu/.hermes/profiles/cs-bot/.env"
    if not os.path.exists(p): return None
    for line in open(p):
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def send_tg(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
    try:
        return urllib.request.urlopen(req, timeout=10).status
    except Exception as e:
        return f"err: {e}"


def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"last_run": None, "last_balance": 0, "last_sweep_tx": None}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(state, open(STATE_FILE, "w"), indent=2)


def main():
    state = load_state()
    now = datetime.now(timezone.utc).isoformat()
    state["last_run"] = now

    usdc = get_usdc_balance(HOT_WALLET)
    eth = get_eth_balance(HOT_WALLET)
    state["last_balance"] = usdc
    print(f"[{now}] hot wallet: {usdc:.4f} USDC | {eth:.6f} ETH")

    # Check threshold
    if usdc < THRESHOLD_USDC:
        print(f"below ${THRESHOLD_USDC} threshold — no sweep")
        save_state(state)
        return

    # De-dupe: if we already swept this exact amount in last 24h, skip
    if state.get("last_sweep_tx") and abs(state.get("last_balance", 0) - usdc) < 0.01:
        # State shows we already swept this amount
        # Only re-sweep if balance has GROWN since last sweep (real new earnings)
        prev_usdc = state.get("last_swept_balance", 0)
        if usdc <= prev_usdc:
            print(f"no new earnings since last sweep (was {prev_usdc:.2f}, now {usdc:.2f}) — skip")
            save_state(state)
            return

    # Check gas
    if eth < MIN_GAS_ETH:
        # Need top-up from main
        print(f"ETH {eth:.6f} below {MIN_GAS_ETH} — need top-up from main")
        # Skip sweep this round; log + alert
        token = get_tg_token()
        if token and state.get("last_alert_gas") != now[:10]:
            send_tg(token, "366983738", f"⚠️ Hot wallet {HOT_WALLET[:10]}… has ${usdc:.2f} USDC but only {eth:.6f} ETH (gas). Need manual top-up to sweep.")
            state["last_alert_gas"] = now[:10]
        save_state(state)
        return

    # Execute sweep
    print(f"sweeping {usdc:.4f} USDC...")
    result = subprocess.run([
        "python3", "/home/ubuntu/.hermes/profiles/bot4/skills/bountybook-earnings/scripts/sweep_safely.py",
        "--sweep", "eth+usdc", "--src", HOT_WALLET, "--dest", MAIN_WALLET,
    ], capture_output=True, text=True, timeout=120)
    out = result.stdout + result.stderr
    print(out)

    # Parse tx hash from output
    import re
    tx_match = re.search(r'0x[0-9a-f]{64}', out)
    tx_hash = tx_match.group(0) if tx_match else None
    state["last_sweep_tx"] = tx_hash
    state["last_swept_balance"] = usdc
    save_state(state)

    # Alert
    token = get_tg_token()
    if token:
        msg = f"💰 Auto-sweep done — ${usdc:.2f} USDC → main wallet\n"
        if tx_hash:
            msg += f"TX: {tx_hash}\nhttps://basescan.org/tx/{tx_hash}"
        send_tg(token, "366983738", msg)


if __name__ == "__main__":
    main()