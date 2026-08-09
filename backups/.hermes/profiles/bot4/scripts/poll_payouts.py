#!/usr/bin/env python3
"""Background BountyBook payout poller. Prints only when USDC balance or job payout changes."""
import json, time, urllib.request

WALLET = "0xD2965001942B7BE86143510dB9945875301e639b"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
API = "https://api.bountybook.ai"

JOB_IDS = [
    "60379d18-2a1b-4d47-b732-0f16840680c0",  # log_parser $3
    "740fd768-1dcb-410c-a7ad-c64ac8be50af",  # flatten $2
    "a0af3d48-327a-4923-b7f3-2ab1cad96dfd",  # versions $2.50
    "784345ae-fd58-481e-93cd-c1f6226ffd0d",  # pubsub $5
    "823eedfb-49f1-4a2c-9fba-87e6c4075e2a",  # bloom $12
    "212e5e5c-4b39-406a-a33e-ffc8b7c20398",  # md_to_html $5
    "87b131ee-7102-4d69-a99d-08cff67e9c1a",  # state_machine $5
    "193daf43-6436-4456-a028-dcb3149a2b95",  # dijkstra $5
    "d6d3d8f1-dfaa-4a4c-9f65-df670bdfdb26",  # dep_resolver $7
    "d47a42b6-8203-4bc7-8bbf-c22ef912c232",  # cicd $7
    "a55bd7d2-b6a0-4bfc-80b5-f788d0ff312d",  # typed_emitter TS $5
    "3994dba9-a6b4-4ef0-bbac-db0455b0faf8",  # min_heap $4
    "fca0ae30-6edc-401d-86dc-69c9681f233f",  # retry $5
    "05972785-3be7-4b20-be73-acd7484767d3",  # rate_limiter $5
    "dc07cac3-ba35-4f13-965e-4fa8ace642a5",  # trie $4
    "9afd2ac3-0c1e-46e8-b420-26c14a1a8687",  # event_emitter $4
    "2597db6c-bf69-4f66-967d-15ddf66ccf29",  # vector_db $4
]


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BizBot/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def eth_call(data):
    req = urllib.request.Request(
        "https://mainnet.base.org",
        data=json.dumps({"jsonrpc": "2.0", "method": "eth_call",
                         "params": [{"to": USDC, "data": data}, "latest"], "id": 1}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "BizBot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

BALANCEOF = "0x70a08231000000000000000000000000" + WALLET[2:]

last_balance = None
last_payouts = {}
while True:
    try:
        r = eth_call(BALANCEOF)
        bal = int(r.get("result", "0x0"), 16) / 1e6
        if last_balance is None:
            last_balance = bal
            print(f"[init] USDC balance: {bal:.6f}", flush=True)
        elif abs(bal - last_balance) > 0.0001:
            print(f"[PAYOUT] USDC {last_balance:.6f} -> {bal:.6f} (+{bal-last_balance:.6f})", flush=True)
            last_balance = bal

        for jid in JOB_IDS:
            try:
                d = http_get(f"{API}/jobs/{jid}")
                ps = d.get("payout_status", "none")
                txh = d.get("payout_tx_hash")
                if ps != "none" and txh and last_payouts.get(jid) != txh:
                    amt = d.get("budget_usdc", "?")
                    print(f"[PAID] {jid[:8]} ${amt} USDC tx={txh}", flush=True)
                    last_payouts[jid] = txh
            except Exception as e:
                pass
    except Exception as e:
        print(f"[poll error] {e}", flush=True)
    time.sleep(60)
