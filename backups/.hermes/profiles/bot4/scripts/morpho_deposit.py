#!/usr/bin/env python3
"""
morpho_deposit.py — deposit USDC into a Morpho (MetaMorpho) ERC-4626 vault on Base.

Vault: Gauntlet USDC Prime (gtUSDCp) 0xeE8F4eC5672F09119b96Ab6fB59C27E1b7e44b61
       — largest USDC vault on Base ($428.8M TVL, 4.12% net APY, verified live).

Modes:
  python3 morpho_deposit.py            # DRY RUN
  python3 morpho_deposit.py --execute  # approve + deposit full USDC balance
  python3 morpho_deposit.py --amount N # deposit specific USDC amount

ERC-4626: approve(USDC->vault) then vault.deposit(assets, receiver).
Uses WALLET_PK from ~/.hermes/.env (hot wallet 0x57E33b...).
"""
import json, os, sys, time, urllib.request

HOT          = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
BASE_USDC    = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
VAULT        = "0xeE8F4eC5672F09119b96Ab6fB59C27E1b7e44b61"  # Gauntlet USDC Prime
BASE_RPC     = "https://base.drpc.org"
BASE_RPC_FB  = ["https://base-rpc.publicnode.com", "https://1rpc.io/base"]

DRY = "--execute" not in sys.argv
AMOUNT_OVERRIDE = None
if "--amount" in sys.argv:
    AMOUNT_OVERRIDE = float(sys.argv[sys.argv.index("--amount") + 1])

ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},{"constant":true,"inputs":[{"name":"","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

VAULT_ABI = json.loads('[{"constant":false,"inputs":[{"name":"assets","type":"uint256"},{"name":"receiver","type":"address"}],"name":"deposit","outputs":[{"name":"shares","type":"uint256"}],"type":"function"},{"constant":true,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":true,"inputs":[{"name":"","type":"address"}],"name":"maxDeposit","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":true,"inputs":[{"name":"assets","type":"uint256"}],"name":"previewDeposit","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')


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
    return int(rpc(rpc_url, "eth_call", [{"to": token, "data": data}, "latest"]), 16)


def main():
    print("=" * 60)
    print("MORPHO DEPOSIT — " + ("DRY RUN (nothing signed)" if DRY else "EXECUTE MODE"))
    print("=" * 60)
    env = load_env()
    pk = env.get("WALLET_PK")
    if not pk:
        print("FATAL: WALLET_PK not found"); sys.exit(1)
    from eth_account import Account
    acct = Account.from_key(pk)
    assert acct.address.lower() == HOT.lower(), f"key derives {acct.address}"

    usdc_raw = balance_of(BASE_RPC, BASE_USDC, HOT)
    usdc = usdc_raw / 1e6
    print(f"Wallet     : {acct.address}")
    print(f"USDC balance: ${usdc:.6f}")

    amount = usdc if AMOUNT_OVERRIDE is None else AMOUNT_OVERRIDE
    if amount <= 0:
        print("No USDC to deposit."); return
    assets = int(amount * 1e6)
    print(f"Deposit    : ${amount:.6f} USDC into Gauntlet USDC Prime")
    print(f"Vault      : {VAULT}")

    # ---- preview shares (read-only) ----
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT), abi=VAULT_ABI)
    try:
        shares = vault.functions.previewDeposit(assets).call()
        print(f"Preview shares: {shares} (~{shares/1e18:.6f} gtUSDCp tokens)")
    except Exception as e:
        print(f"previewDeposit warn: {e}")

    if DRY:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE — nothing signed/broadcast.")
        print("Execute: python3 morpho_deposit.py --execute")
        print("=" * 60)
        return

    # ---- execute ----
    print("\n--- EXECUTING ---")
    usdc_c = w3.eth.contract(address=Web3.to_checksum_address(BASE_USDC), abi=ERC20_ABI)

    def send_tx(w3i, tx):
        tx["from"] = acct.address
        tx["nonce"] = w3i.eth.get_transaction_count(acct.address)
        if tx.get("to") and isinstance(tx["to"], str):
            tx["to"] = Web3.to_checksum_address(tx["to"])
        if "maxFeePerGas" not in tx and "gasPrice" not in tx:
            tx["gasPrice"] = w3i.eth.gas_price
        if "gas" not in tx:
            tx["gas"] = w3i.eth.estimate_gas(tx)
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3i.eth.send_raw_transaction(raw)
        print(f"  tx {h.hex()} ... waiting")
        deadline = time.time() + 180
        rec = None
        while time.time() < deadline:
            try:
                rec = w3i.eth.get_transaction_receipt(h)
                if rec is not None: break
            except Exception: pass
            time.sleep(5)
        if rec is None:
            print(f"  WARN: no receipt yet {h.hex()}")
        else:
            print(f"  confirmed {h.hex()[:20]}... status={rec.get('status')}")
        return h

    # 1. approve
    print("  approving USDC -> vault ...")
    tx = usdc_c.functions.approve(Web3.to_checksum_address(VAULT), assets).build_transaction({"from": acct.address})
    send_tx(w3, tx)

    # 2. deposit
    print("  depositing ...")
    tx = vault.functions.deposit(assets, acct.address).build_transaction({"from": acct.address})
    send_tx(w3, tx)

    # 3. verify
    time.sleep(5)
    print("\n--- POST-DEPOSIT ---")
    print(f"USDC left    : ${balance_of(BASE_RPC, BASE_USDC, HOT)/1e6:.6f}")
    share_raw = 0
    try:
        share_raw = vault.functions.balanceOf(acct.address).call()
    except Exception as e:
        print(f"share read warn: {e}")
    print(f"Vault shares : {share_raw/1e18:.6f} gtUSDCp")
    print("DONE")


if __name__ == "__main__":
    main()
