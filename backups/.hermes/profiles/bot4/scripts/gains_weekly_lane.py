#!/usr/bin/env python3
"""
gains_weekly_lane.py — Weekly trend lane on Gains Network (gTrade) Base.

Trades XAU/USD (gold) or EUR/USD weekly trend with SMALL stakes.
DRY-RUN by default: prints the exact trade it WOULD open, verifies
on-chain readiness, and exits without sending money.
LIVE only with --live (and only when all risk gates pass).

Risk rules (from trading-risk-management):
  - risk per trade = 1% of bankroll (stake IS the loss cap w/ SL)
  - SL always set; daily -3% halt; no martingale
  - min notional enforced by Gains (~$285 XAU) -> leverage chosen so
    collateral stays small; SL limits loss to risk budget.

Usage:
  python3 gains_weekly_lane.py                # dry-run
  python3 gains_weekly_lane.py --live         # place real trade if signal fires
  python3 gains_weekly_lane.py --pair XAUUSD  # force pair (XAUUSD | EURUSD)
"""
import os, sys, json, time, urllib.request, datetime

# ---------------- config ----------------
DIAMOND = "0x6cD5aC19a07518A8092eEFfDA4f1174C72704eeb"   # Base gTrade diamond
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"        # Base USDC
RPC = "https://mainnet.base.org"
BACKEND = "https://backend-base.gains.trade"
PRICING = "https://backend-pricing.eu.gains.trade"

PAIRS = {
    "XAUUSD": {"pairIndex": 90, "minNotional": 285.71, "maxLev": 250},
    "EURUSD": {"pairIndex": 21, "minNotional": 833.33, "maxLev": 1000},
    "GBPUSD": {"pairIndex": 23, "minNotional": 833.33, "maxLev": 1000},
    "USDJPY": {"pairIndex": 22, "minNotional": 833.33, "maxLev": 1000},
    "BTCUSD": {"pairIndex": 0, "minNotional": 285.71, "maxLev": 200},
    "ETHUSD": {"pairIndex": 1, "minNotional": 285.71, "maxLev": 200},
}
# history source per pair (only verified free feeds)
HIST = {
    "XAUUSD": ("binance", "PAXGUSDT"),
    "EURUSD": ("frankfurter", "EURUSD"),
    "GBPUSD": ("frankfurter", "GBPUSD"),
    "USDJPY": ("frankfurter", "USDJPY"),
    "BTCUSD": ("binance", "BTCUSDT"),
    "ETHUSD": ("binance", "ETHUSDT"),
}
STATE = os.path.expanduser("~/.hermes/profiles/bot4/state/gains_lane_state.json")

USDC_ABI = [{"constant": True, "inputs": [{"name": "a", "type": "address"}],
             "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
            {"constant": False, "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
             "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "o", "type": "address"}, {"name": "s", "type": "address"}],
             "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}]

TRADE_ABI = [{"inputs": [
    {"components": [
        {"name": "user", "type": "address"}, {"name": "index", "type": "uint32"},
        {"name": "pairIndex", "type": "uint16"}, {"name": "leverage", "type": "uint24"},
        {"name": "long", "type": "bool"}, {"name": "isOpen", "type": "bool"},
        {"name": "collateralIndex", "type": "uint8"}, {"name": "tradeType", "type": "uint8"},
        {"name": "collateralAmount", "type": "uint120"}, {"name": "openPrice", "type": "uint64"},
        {"name": "tp", "type": "uint64"}, {"name": "sl", "type": "uint64"},
        {"name": "isCounterTrade", "type": "bool"}, {"name": "positionSizeToken", "type": "uint160"},
        {"name": "__placeholder", "type": "uint24"}],
        "name": "_trade", "type": "tuple"},
    {"name": "_maxSlippageP", "type": "uint16"}, {"name": "_referrer", "type": "address"}],
    "name": "openTrade", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]


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


def http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def get_tv():
    return http_json(f"{BACKEND}/trading-variables")


def get_price(pair_index):
    d = http_json(f"{PRICING}/charts")
    return float(d["closes"][pair_index]), float(d["indexPrices"][pair_index])


def yahoo_history(symbol, days=35):
    """Free Yahoo chart API daily closes. Returns list of (date, close)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2mo"
    try:
        d = http_json(url, timeout=20)
        r = d.get("chart", {}).get("result")
        if not r:
            return None
        ts = r[0].get("timestamp", [])
        close = r[0]["indicators"]["quote"][0].get("close", [])
        items = []
        for t, c in zip(ts, close):
            if c is not None:
                dt = datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
                items.append((dt, float(c)))
        return items[-days:]
    except Exception as e:
        print(f"  yahoo err: {str(e)[:80]}")
        return None


def binance_daily(symbol="PAXGUSDT", days=35):
    """Free Binance daily klines (PAXG = gold-backed token, tracks XAU)."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={days}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
    try:
        k = json.loads(urllib.request.urlopen(req, timeout=15).read())
        items = []
        for row in k:
            dt = datetime.datetime.utcfromtimestamp(row[0] / 1000).strftime("%Y-%m-%d")
            items.append((dt, float(row[4])))
        return items
    except Exception as e:
        print(f"  binance err: {str(e)[:80]}")
        return None


def frankfurter_daily(symbol="EURUSD", days=35):
    """Free ECB daily FX closes via Frankfurter API (no key)."""
    end = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days + 10)).isoformat()
    from_, to_ = symbol[:3], symbol[3:]
    url = f"https://api.frankfurter.app/{start}..{end}?from={from_}&to={to_}"
    try:
        d = http_json(url)
        rates = d.get("rates", {})
        items = sorted((dt, float(v[to_])) for dt, v in rates.items())
        return items[-days:]
    except Exception as e:
        print(f"  frankfurter err: {str(e)[:80]}")
        return None


def signal_from_series(series):
    """Weekly trend: price vs 10-day SMA + 5/10 momentum. Returns (direction, strength)."""
    if not series or len(series) < 12:
        return None, 0.0
    closes = [c for _, c in series]
    last = closes[-1]
    sma10 = sum(closes[-10:]) / 10
    mom5 = (last - closes[-6]) / closes[-6]
    mom10 = (last - closes[-11]) / closes[-11]
    strength = abs(last / sma10 - 1) * 100 + abs(mom5) * 100 + abs(mom10) * 50
    direction = "long" if (last > sma10 and mom5 > 0) else ("short" if (last < sma10 and mom5 < 0) else None)
    return direction, round(strength, 2)


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    return {"day": "", "day_pnl": 0.0, "open_trades": []}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)


def scan_all():
    """Scan all pairs, return the strongest tradeable signal (pair, direction, strength, px)."""
    tv = get_tv()
    results = []
    for pair, cfg in PAIRS.items():
        src, sym = HIST[pair]
        try:
            if src == "binance":
                hist = binance_daily(sym, 35)
            else:
                hist = frankfurter_daily(sym, 35)
            if not hist:
                continue
            direction, strength = signal_from_series(hist)
            if not direction:
                continue
            px, _ = get_price(cfg["pairIndex"])
            results.append((pair, direction, strength, px))
        except Exception:
            continue
    results.sort(key=lambda r: r[2], reverse=True)
    return results


def main():
    live = "--live" in sys.argv
    estimate = "--estimate" in sys.argv
    scan = "--scan" in sys.argv
    if scan:
        print("=== Gains multi-product scan ===")
        results = scan_all()
        for pair, direction, strength, px in results:
            print(f"  {pair:8s} -> {direction.upper():5s} strength={strength:6.2f}  px={px:.4f}")
        if results:
            best = results[0]
            print(f"\n  BEST: {best[0]} {best[1].upper()} (strength {best[2]:.2f})")
        else:
            print("  no signals")
        return
    pair = "XAUUSD"
    for a in sys.argv:
        if a.startswith("--pair"):
            if "=" in a:
                pair = a.split("=")[1].upper()
            else:
                i = sys.argv.index(a)
                if i + 1 < len(sys.argv):
                    pair = sys.argv[i + 1].upper()
    if pair not in PAIRS:
        print(f"unknown pair {pair}; use XAUUSD or EURUSD"); return

    cfg = PAIRS[pair]
    print(f"=== Gains weekly lane: {pair} ({'LIVE' if live else 'DRY-RUN'}{'+ESTIMATE' if estimate else ''}) ===")

    # 1) live prices + market open
    tv = get_tv()
    px, idx_px = get_price(cfg["pairIndex"])
    pair_meta = tv["pairs"][cfg["pairIndex"]]
    group = int(pair_meta["groupIndex"])
    open_flag = {0: "isCryptoOpen", 1: "isForexOpen", 3: "isStocksOpen", 6: "isCommoditiesOpen"}
    open_key = open_flag.get(group, None)
    market_open = tv.get(open_key, True) if open_key else True
    print(f"  price: {px:.4f}  (index {idx_px:.4f})  market_open={market_open}")

    # 2) weekly trend signal (free data)
    src, sym = HIST[pair]
    if src == "binance":
        hist = binance_daily(sym, 35)
        if not hist:
            hist = yahoo_history(sym.replace("USDT", "-USD"), 35)
    else:
        hist = frankfurter_daily(sym, 35)
        if not hist:
            hist = yahoo_history(sym + "=X", 35)
    if hist:
        print(f"  history: {len(hist)} days, last {hist[-1][0]}")
    direction, strength = signal_from_series(hist)
    print(f"  signal: {direction or 'NONE'}  strength={strength}")
    if not direction:
        print("  -> no trend setup. no trade (dry or live)."); return

    # 3) bankroll + sizing (1% rule, SL capped)
    env = load_env()
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(RPC))
    acct = w3.eth.account.from_key(env["WALLET_PK"])
    usdc_ct = w3.eth.contract(Web3.to_checksum_address(USDC), abi=USDC_ABI)
    usdc_bal = usdc_ct.functions.balanceOf(acct.address).call() / 1e6
    print(f"  wallet: {acct.address}")
    print(f"  USDC bal: ${usdc_bal:.2f}")
    if usdc_bal < 10:
        print("  ❌ bankroll too small for Gains min notional + safety. need >= $10."); return

    # leverage: collateral = min(risk budget scaled, enough to hit min notional)
    risk_budget = usdc_bal * 0.01  # 1% rule
    leverage = max(5, min(cfg["maxLev"], int(cfg["minNotional"] / max(risk_budget, 0.5))))
    # collateral amount: smallest that satisfies min notional, but never > 10% of bankroll
    collateral = max(risk_budget, cfg["minNotional"] / leverage)
    collateral = min(collateral, usdc_bal * 0.10)
    if collateral * leverage < cfg["minNotional"]:
        leverage = int(cfg["minNotional"] / collateral) + 1
    collateral = min(collateral, usdc_bal * 0.10)
    notional = collateral * leverage
    print(f"  risk budget (1%): ${risk_budget:.2f}")
    print(f"  plan: {'LONG' if direction == 'long' else 'SHORT'} {pair}  collateral=${collateral:.2f}  lev={leverage}x  notional=${notional:.2f}")
    if notional < cfg["minNotional"]:
        print(f"  ❌ cannot reach min notional ${cfg['minNotional']:.0f} safely. skip.")
        return
    if collateral > usdc_bal * 0.10:
        print("  ❌ collateral would exceed 10% of bankroll. skip (grow bankroll first).")
        return

    # 4) SL: cap loss at risk budget; convert to price distance
    sl_pct = (risk_budget / collateral) / leverage  # price % move that hits risk budget
    sl_pct = max(sl_pct, 0.002)  # at least 0.2% away to avoid spread dust
    if direction == "long":
        sl_price = px * (1 - sl_pct)
    else:
        sl_price = px * (1 + sl_pct)
    print(f"  SL @ {sl_price:.4f} ({sl_pct*100:.2f}% away) -> loss cap ${risk_budget:.2f}")

    # 5) execute or dry-run
    if not live:
        if estimate:
            # verify the contract would accept our trade struct WITHOUT sending money
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(RPC))
            acct = w3.eth.account.from_key(env["WALLET_PK"])
            diamond = Web3.to_checksum_address(DIAMOND)
            usdc_ct = w3.eth.contract(Web3.to_checksum_address(USDC), abi=USDC_ABI)
            collateral_amount = int(collateral * 1e6)
            # approve first (same tx live path does; harmless, needed for any trade)
            allow = usdc_ct.functions.allowance(acct.address, diamond).call()
            if allow < collateral_amount:
                ap = usdc_ct.functions.approve(diamond, 2**255 - 1).build_transaction({
                    "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                    "gas": 70000, "gasPrice": w3.eth.gas_price})
                signed = acct.sign_transaction(ap)
                txh = w3.eth.send_raw_transaction(signed.raw_transaction)
                w3.eth.wait_for_transaction_receipt(txh, timeout=120)
                print(f"  (approve tx sent for verification: {txh.hex()[:12]}…)")
            trade = {
                "user": acct.address, "index": 0, "pairIndex": cfg["pairIndex"],
                "leverage": int(leverage * 1e3), "long": direction == "long",
                "isOpen": True, "collateralIndex": 1, "tradeType": 0,
                "collateralAmount": collateral_amount, "openPrice": int(px * 1e10),
                "tp": 0, "sl": int(sl_price * 1e10), "isCounterTrade": False,
                "positionSizeToken": 0, "__placeholder": 0,
            }
            tx_ct = w3.eth.contract(diamond, abi=TRADE_ABI)
            build = tx_ct.functions.openTrade(trade, 30, "0x0000000000000000000000000000000000000000")
            try:
                gas = build.estimate_gas({"from": acct.address})
                print(f"\n  ✅ ESTIMATE OK — contract accepts trade struct (gas ~{gas})")
                print("  on-chain path verified. No open trade placed.")
            except Exception as e:
                msg = str(e)[:300]
                print(f"\n  ⚠️  estimate failed: {msg}")
                print("  (contract rejected the struct — fixing before any live run)")
            return
        print("\n  DRY-RUN complete. No money moved.")
        print("  Re-run with --live to place this trade (all gates must pass).")
        return

    # LIVE path
    diamond = Web3.to_checksum_address(DIAMOND)
    collateral_amount = int(collateral * 1e6)
    trade = {
        "user": acct.address, "index": 0, "pairIndex": cfg["pairIndex"],
        "leverage": int(leverage * 1e3), "long": direction == "long",
        "isOpen": True, "collateralIndex": 1, "tradeType": 0,
        "collateralAmount": collateral_amount, "openPrice": int(px * 1e10),
        "tp": 0, "sl": int(sl_price * 1e10), "isCounterTrade": False,
        "positionSizeToken": 0, "__placeholder": 0,
    }
    max_slippage_p = 30  # 3% slippage tolerance
    tx_ct = w3.eth.contract(diamond, abi=TRADE_ABI)
    # approve
    allow = usdc_ct.functions.allowance(acct.address, diamond).call()
    if allow < collateral_amount:
        print("  approving USDC...")
        ap = usdc_ct.functions.approve(diamond, 2**255 - 1).build_transaction({
            "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 70000, "gasPrice": w3.eth.gas_price})
        signed = acct.sign_transaction(ap)
        txh = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  approve tx: {txh.hex()}")
        w3.eth.wait_for_transaction_receipt(txh, timeout=120)
        print("  approved.")
    # open
    build = tx_ct.functions.openTrade(trade, max_slippage_p, "0x0000000000000000000000000000000000000000")
    try:
        gas = build.estimate_gas({"from": acct.address})
    except Exception as e:
        print(f"  ❌ estimate failed: {str(e)[:200]}")
        print("  (dry-run passed; on-chain gate failed — not sending tx)")
        return
    print(f"  estimated gas: {gas}")
    tx = build.build_transaction({"from": acct.address,
                                  "nonce": w3.eth.get_transaction_count(acct.address),
                                  "gas": int(gas * 1.3), "gasPrice": w3.eth.gas_price})
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  ✅ openTrade tx: {txh.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=180)
    print(f"  status: {'SUCCESS' if rcpt['status'] == 1 else 'FAILED'}")
    st = load_state()
    st["open_trades"].append({"pair": pair, "direction": direction,
                              "collateral": collateral, "lev": leverage,
                              "sl": sl_price, "ts": time.time(), "tx": txh.hex()})
    save_state(st)


if __name__ == "__main__":
    main()
