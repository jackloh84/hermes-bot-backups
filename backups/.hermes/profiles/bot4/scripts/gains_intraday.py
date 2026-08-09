#!/usr/bin/env python3
"""
gains_intraday.py — Multi-product 30-min trend trader on Gains Network (Base).
Jack's directives (Aug 7 2026):
  - Trade LONG on short timeframe (30m/1h), keep an eye on it every minute
  - Stop the day once win rate hits 50-60% with profit banked
  - DON'T only trade gold — take advantage of the other products too
Jack's directives (Aug 8 2026):
  - STRONG-ONLY: require strength >= MIN_STRENGTH before opening (weak = skip)
  - 2-WAY: strong BULL signal -> LONG (price up), strong BEAR signal -> SHORT (price down)

Products (30m free data verified on Binance):
  XAUUSD (PAXG proxy), BTCUSD, ETHUSD. FX majors (EUR/GBP/JPY) excluded —
  Frankfurter only has DAILY data, no reliable free 30m FX feed.

Design (backtested PAXG 30m, ~30 days):
  - Signal: close vs EMA20 + 3-bar momentum (LONG if above & up, SHORT if below & down)
  - Scans ALL products, trades the STRONGEST signal
  - TP = entry +/- 1.5 x ATR(14) ; SL = entry +/- 1.0 x ATR(14)   [+4.7% backtest]
  - Opens DIRECTLY (not via lane) so SL is ATR-based, NOT the 0.2% trap
  - WR-stop rule: wins >= losses AND day realized > 0 -> STOP for the day
  - Daily -3% hard stop; max 8 trades/day

Usage:
  python3 gains_intraday.py            # monitor + act (silent if holding/quiet)
  python3 gains_intraday.py --status   # report only
"""
import os, sys, json, time, datetime, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gains_weekly_lane as g

NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify_feishu.py")


def notify_feishu(text):
    """Fire-and-forget Feishu alert — never blocks trading."""
    try:
        import subprocess
        subprocess.Popen(["python3", NOTIFY, text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

RPC = g.RPC
DIAMOND = g.DIAMOND
USDC = g.USDC
BACKEND = g.BACKEND
PRICING = g.PRICING
# ABSOLUTE path — cron HOME differs from shell HOME (nested-path bug fix)
STATE = "/home/ubuntu/.hermes/profiles/bot4/state/gains_intraday_state.json"
WALLET = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"

INTERVAL = "30m"
MAX_TRADES_DAY = 8
TP_ATR = 1.5
SL_ATR = 1.0
DAILY_LOSS_STOP = 0.03   # -3% bankroll halt
WR_STOP_MIN = 0.5        # stop when wins/(wins+losses) >= 0.5 (Jack: 50-60%)
LONG_ONLY = False        # Jack Aug 8: 2-way — strong BULL->long, strong BEAR->short
MIN_STRENGTH = 0.0       # FILTERS OFF (Jack Aug 9: rebuild from scratch — trade every directional signal)
# Jack rule Aug 7: profit-lock threshold is OUR discretion based on confidence —
#   strength >= 1.2 -> confident -> ride to 100% TP
#   strength 0.8-1.2 -> medium -> lock 70%
#   strength < 0.8 -> weak -> lock 50% (bank early, don't risk reversal)
def lock_for_strength(strength):
    if strength >= 1.2:
        return 1.0    # full TP
    if strength >= 0.8:
        return 0.7    # 70%
    return 0.5        # 50%
HEARTBEAT_MIN = 30       # while holding, ping Jack every 30 min so he never wonders if we forgot

# pair: (binance symbol, pairIndex, minNotional, maxLev, collateral, interval)
# interval = backtested best timeframe per product (Aug 7 2026, 2-way TP1.5xATR/SL1.0xATR):
#   XAU 30m +5.2% (1h -1.2%) | BTC 1h +19.1% (30m -7.5%) | ETH 1h +12.7% (30m -7.1%)
PRODUCTS = {
    "ETHUSD": ("ETHUSDT", 1, 285.71, 200, 1.43, "1h"),
}

CLOSE_ABI = [{"inputs": [{"name": "_index", "type": "uint32"},
                         {"name": "_expectedPrice", "type": "uint64"}],
              "name": "closeTradeMarket", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]


def http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def binance_klines(symbol="PAXGUSDT", interval="30m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
    k = json.loads(urllib.request.urlopen(req, timeout=15).read())
    out = []
    for row in k:
        out.append((datetime.datetime.utcfromtimestamp(row[0] / 1000), float(row[1]), float(row[2]), float(row[3]), float(row[4])))
    return out


def ema_vals(closes, n=20):
    k = 2 / (n + 1)
    e = closes[0]
    out = []
    for c in closes:
        e = c * k + e * (1 - k)
        out.append(e)
    return out


def atr_vals(bars, n=14):
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i][2], bars[i][3], bars[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atrs = []
    for i in range(len(bars)):
        if i < n:
            atrs.append(float("nan"))
        else:
            atrs.append(sum(trs[i - n:i]) / n)
    return atrs


def get_signals(include_all=False):
    """20-bar Donchian BREAKOUT (Jack Aug 9 — backtest champion on ETH 1h,
    +11.1% on Gains). Shared signal code from trading_engine so live == backtest.
    Returns [(pair, direction, strength, atr, atr_pct, px)] sorted by strength.
    """
    try:
        import trading_engine as te
    except Exception:
        return []
    results = []
    for pair, (sym, pidx, _, _, _, interval) in PRODUCTS.items():
        try:
            bars = te.fetch_klines(sym, interval, 10)
            if len(bars) < 30:
                continue
            s = te.last_signal(bars, "breakout")
            if s == 0:
                continue
            direction = "long" if s == 1 else "short"
            atrs = te.atr(bars, 14)
            atr = atrs[-1] if atrs[-1] == atrs[-1] else bars[-1]["c"] * 0.003  # nan guard
            px = bars[-1]["c"]
            strength = abs(px / bars[-10]["c"] - 1) * 100  # proxy: 10-bar move
            atr_pct = atr / px * 100
            results.append((pair, direction, round(strength, 2), atr, round(atr_pct, 3), px))
        except Exception:
            continue
    results.sort(key=lambda r: r[2], reverse=True)
    return results


def get_open_trade():
    d = http_json(f"{BACKEND}/open-trades")
    for t in d:
        tr = t.get("trade", {})
        if str(tr.get("user", "")).lower() == WALLET.lower():
            return tr
    return None


def get_price(pair_index):
    d = http_json(f"{PRICING}/charts")
    return float(d["closes"][pair_index]), float(d["indexPrices"][pair_index])


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    today = datetime.date.today().isoformat()
    return {"day": today, "trades": 0, "wins": 0, "losses": 0,
            "realized": 0.0, "bankroll": 52.33, "stopped": False, "open": None,
            "last_ping": 0.0, "trade_log": []}


def log_trade(st, pair, direction, entry, tp, sl, collateral, leverage, strength, lock_pct, result, pnl):
    """Append a finished trade to state.trade_log for the Feishu sheet + history."""
    st.setdefault("trade_log", []).append({
        "ts": time.time(), "pair": pair, "direction": direction, "entry": entry,
        "tp": tp, "sl": sl, "collateral": collateral, "leverage": leverage,
        "strength": strength, "lock_pct": lock_pct, "result": result, "pnl": pnl,
    })


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)


def roll_day(st):
    today = datetime.date.today().isoformat()
    if st.get("day") != today:
        st["day"] = today
        st["trades"] = 0
        st["wins"] = 0
        st["losses"] = 0
        st["realized"] = 0.0
        st["stopped"] = False
        save_state(st)
    return st


def wr_text(st):
    total = st["wins"] + st["losses"]
    pct = (st["wins"] / total * 100) if total else 0.0
    return f"{st['wins']}W/{st['losses']}L ({pct:.0f}%)"


def main():
    status_only = "--status" in sys.argv

    env = g.load_env()
    st = load_state()
    st = roll_day(st)
    lines = []

    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(RPC))
    acct = w3.eth.account.from_key(env["WALLET_PK"])
    diamond = Web3.to_checksum_address(DIAMOND)

    trade = get_open_trade()

    # -------- 1) position open? manage TP/SL --------
    if trade:
        idx = int(trade.get("index", 0))
        op = float(trade.get("openPrice", 0) or 0) / 1e10
        long = trade.get("long", True)
        coll = float(trade.get("collateralAmount", 0) or 0) / 1e6
        pidx = int(trade.get("pairIndex", 90))
        pair_name = next((p for p, cfg in PRODUCTS.items() if cfg[1] == pidx), f"PAIR{pidx}")
        lev = float(trade.get("leverage", 0) or 0) / 1e3 or 250
        px, _ = get_price(pidx)
        # TP/SL from our state (ATR-based); fallback to ATR estimate
        if st.get("open") and st["open"].get("tp"):
            tp = st["open"]["tp"]
            sl = st["open"]["sl"]
        else:
            atr_est = (op * 0.0025)
            tp = op * (1 + TP_ATR * (atr_est / op))
            sl = op * (1 - SL_ATR * (atr_est / op))
        # PnL on collateral INCLUDES leverage: price_move% × lev × collateral
        pnl_coll = ((px - op) / op) * lev * coll if long else ((op - px) / op) * lev * coll
        if status_only:
            lines.append(f"open {'LONG' if long else 'SHORT'} {pair_name} @{op:.2f} now {px:.2f} (PnL ~${pnl_coll:.2f})")
            lines.append(f"TP @ {tp:.2f} | SL @ {sl:.2f}")
            lines.append(f"day: {wr_text(st)} | realized ${st['realized']:+.2f} | trades {st['trades']}/{MAX_TRADES_DAY}")
            print("\n".join(lines)); return

        # Progress toward TP (0..1+): how far price has moved entry->TP
        progress = ((px - op) / (tp - op)) if long else ((op - px) / (op - tp))
        progress = max(progress, 0.0)  # negative (against us) -> 0

        # Per-trade profit-lock threshold (set at open from signal confidence)
        lock_pct = (st.get("open") or {}).get("lock_pct", 0.5)

        # -------- Jack's profit-lock rule: close at >= lock_pct of TP distance --------
        # If we're already at/above TP, the TP branch below handles it (full win).
        # This branch banks a partial win BEFORE the price can reverse.
        if progress >= lock_pct and not ((long and px >= tp) or (not long and px <= tp)):
            ct = w3.eth.contract(diamond, abi=CLOSE_ABI)
            exp = int(px * 1e10)
            try:
                gas = ct.functions.closeTradeMarket(idx, exp).estimate_gas({"from": acct.address})
            except Exception as e:
                lines.append(f"close estimate fail: {str(e)[:100]}")
                print("\n".join(lines)); return
            txb = ct.functions.closeTradeMarket(idx, exp).build_transaction({
                "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": int(gas * 1.3), "gasPrice": w3.eth.gas_price})
            signed = acct.sign_transaction(txb)
            txh = w3.eth.send_raw_transaction(signed.raw_transaction)
            rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=180)
            ok = rcpt["status"] == 1
            win = pnl_coll if ok else 0.0
            st["trades"] += 1
            st["wins"] += 1 if ok else 0
            st["losses"] += 0 if ok else 1
            st["realized"] += win
            st["bankroll"] += win
            log_trade(st, pair_name, "LONG" if long else "SHORT", op, tp, sl,
                      coll, lev, st.get("open", {}).get("strength", 0),
                      lock_pct, "PROFIT-LOCK" if ok else "ERR", win)
            st["open"] = None
            save_state(st)
            lines.append(f"💰 PROFIT-LOCK CLOSED {'LONG' if long else 'SHORT'} {pair_name} at {progress*100:.0f}% to TP — banked +${win:.2f} (day {wr_text(st)}, realized ${st['realized']:+.2f})")
            notify_feishu(f"💰 GAINS PROFIT-LOCK: closed {'LONG' if long else 'SHORT'} {pair_name} @{px:.2f} ({progress*100:.0f}% to TP)\nBanked +${win:.2f} | Day {wr_text(st)} | Realized ${st['realized']:+.2f}")
            if st["wins"] >= st["losses"] and st["realized"] > 0 and st["wins"] > 0:
                st["stopped"] = True
                save_state(st)
                lines.append(f"🛑 WIN-RATE STOP hit ({wr_text(st)}) — profit banked, done for today")
                notify_feishu(f"🛑 GAINS WIN-RATE STOP ({wr_text(st)}) — profit banked, done for today")
            print("\n".join(lines)); return

        # TP hit?
        if (long and px >= tp) or (not long and px <= tp):
            ct = w3.eth.contract(diamond, abi=CLOSE_ABI)
            exp = int(px * 1e10)
            try:
                gas = ct.functions.closeTradeMarket(idx, exp).estimate_gas({"from": acct.address})
            except Exception as e:
                lines.append(f"close estimate fail: {str(e)[:100]}")
                print("\n".join(lines)); return
            txb = ct.functions.closeTradeMarket(idx, exp).build_transaction({
                "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": int(gas * 1.3), "gasPrice": w3.eth.gas_price})
            signed = acct.sign_transaction(txb)
            txh = w3.eth.send_raw_transaction(signed.raw_transaction)
            rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=180)
            ok = rcpt["status"] == 1
            win = pnl_coll if ok else 0.0
            st["trades"] += 1
            st["wins"] += 1 if ok else 0
            st["losses"] += 0 if ok else 1
            st["realized"] += win
            st["bankroll"] += win
            log_trade(st, pair_name, "LONG" if long else "SHORT", op, tp, sl,
                      coll, lev, st.get("open", {}).get("strength", 0),
                      lock_pct, "TP" if ok else "ERR", win)
            st["open"] = None
            save_state(st)
            lines.append(f"✅ TP CLOSED {'LONG' if long else 'SHORT'} {pair_name} tx {txh.hex()[:16]}…  banked +${win:.2f} (day {wr_text(st)}, realized ${st['realized']:+.2f})")
            notify_feishu(f"✅ GAINS TP HIT: closed {'LONG' if long else 'SHORT'} {pair_name} @{px:.2f}\nBanked +${win:.2f} | Day {wr_text(st)} | Realized ${st['realized']:+.2f}")
            if st["wins"] >= st["losses"] and st["realized"] > 0 and st["wins"] > 0:
                st["stopped"] = True
                save_state(st)
                lines.append(f"🛑 WIN-RATE STOP hit ({wr_text(st)}) — profit banked, done for today")
                notify_feishu(f"🛑 GAINS WIN-RATE STOP ({wr_text(st)}) — profit banked, done for today")
        # SL hit (position still visible but price past our ATR SL)
        elif (long and px <= sl) or (not long and px >= sl):
            # REAL loss at SL: collateral × lev × (SL distance / entry)
            loss = -coll * lev * (abs(op - sl) / op)
            st["trades"] += 1
            st["losses"] += 1
            st["realized"] += loss
            st["bankroll"] += loss
            log_trade(st, pair_name, "LONG" if long else "SHORT", op, tp, sl,
                      coll, lev, st.get("open", {}).get("strength", 0),
                      st.get("open", {}).get("lock_pct", 0.5), "SL", loss)
            st["open"] = None
            save_state(st)
            lines.append(f"❌ SL HIT {'LONG' if long else 'SHORT'} {pair_name} (now {px:.2f}) — loss ${loss:.2f} (day {wr_text(st)})")
            notify_feishu(f"❌ GAINS SL HIT: {'LONG' if long else 'SHORT'} {pair_name} closed at SL\nLoss -${abs(loss):.2f} | Day {wr_text(st)} | Realized ${st['realized']:+.2f}")
        # else holding — heartbeat ping so Jack never wonders if we forgot
        else:
            now = time.time()
            last = st.get("last_ping", 0.0)
            if not status_only and now - last >= HEARTBEAT_MIN * 60:
                st["last_ping"] = now
                save_state(st)
                lines.append(f"👁️ Watching {'LONG' if long else 'SHORT'} {pair_name} @{op:.2f} now {px:.2f} ({progress*100:.0f}% to TP) — PnL ~${pnl_coll:.2f}, TP @ {tp:.2f}")
    # -------- 2) no position: check SL auto-hit or reopen --------
    else:
        if st.get("open") and not status_only:
            o = st["open"]
            op = o.get("entry", 0)
            sl = o.get("sl", 0)
            coll = o.get("collateral", 1.14)
            lev = o.get("leverage", 250)
            long_dir = o.get("direction", "long") == "long"
            # REAL loss at SL: collateral × lev × (SL distance / entry)
            loss = -coll * lev * (abs(op - sl) / op) if op else -0.01
            st["trades"] += 1
            st["losses"] += 1
            st["realized"] += loss
            st["bankroll"] += loss
            log_trade(st, o.get("pair", "?"), o.get("direction", "long").upper(),
                      op, o.get("tp", 0), sl, coll, lev, o.get("strength", 0),
                      o.get("lock_pct", 0.5), "SL-AUTO", loss)
            st["open"] = None
            save_state(st)
            lines.append(f"❌ SL AUTO-HIT (position closed on-chain) — loss ${loss:.2f} (day {wr_text(st)})")
            notify_feishu(f"❌ GAINS SL AUTO-HIT: {o.get('direction','?').upper()} {o.get('pair','?')} closed on-chain\nLoss -${abs(loss):.2f} | Day {wr_text(st)} | Realized ${st['realized']:+.2f}")

        if status_only:
            lines.append(f"no position. last: {wr_text(st)} | realized ${st['realized']:+.2f} | bankroll ${st['bankroll']:.2f}")
            lines.append(f"filter: {'LONG-ONLY' if LONG_ONLY else '2-way'} + strength >= {MIN_STRENGTH}")
            sigs = get_signals(include_all=True)
            for pair, direction, strength, atr, atr_pct, px in sigs[:6]:
                passes = (direction == "long" and strength >= MIN_STRENGTH) if LONG_ONLY else strength >= MIN_STRENGTH
                mark = " ✅" if passes else " ❌"
                lines.append(f"  {pair:8s} {direction.upper():5s} strength={strength:6.2f} ATR%={atr_pct:.2f} px={px:.2f}{mark}")
            if sigs:
                b = sigs[0]
                lines.append(f"  BEST: {b[0]} {b[1].upper()} (strength {b[2]:.2f})")
            else:
                lines.append("  no signals")
            print("\n".join(lines)); return

        if st.get("stopped"):
            lines.append(f"🛑 already stopped for the day (WR {wr_text(st)}, realized ${st['realized']:+.2f})")
            print("\n".join(lines)); return
        if st["trades"] >= MAX_TRADES_DAY:
            lines.append(f"🛑 trade cap {MAX_TRADES_DAY}/day reached — done for today")
            print("\n".join(lines)); return
        if st["realized"] <= -DAILY_LOSS_STOP * st["bankroll"]:
            lines.append(f"🛑 daily -3% stop — no new trade today")
            print("\n".join(lines)); return

        sigs = get_signals()
        if not sigs:
            return  # silent — no signal
        pair, direction, strength, atr, atr_pct, px = sigs[0]
        sym, pidx, min_notional, max_lev, base_coll, interval = PRODUCTS[pair]

        # -------- OPEN DIRECTLY with ATR-based SL (not the lane's 0.2% trap) --------
        leverage = min(max_lev, int(min_notional / base_coll) + 1) if base_coll * max_lev < min_notional else max_lev
        collateral = max(base_coll, min_notional / leverage)
        sl_dist = SL_ATR * atr
        tp_dist = TP_ATR * atr
        if direction == "long":
            sl_price = px - sl_dist
            tp_price = px + tp_dist
        else:
            sl_price = px + sl_dist
            tp_price = px - tp_dist
        lines.append(f"signal {direction.upper()} {pair} ({interval}) strength {strength} ATR {atr:.2f} ({atr_pct}%) — opening")
        lines.append(f"  collateral=${collateral:.2f} lev={leverage}x notional=${collateral*leverage:.2f}")

        usdc_ct = w3.eth.contract(Web3.to_checksum_address(USDC), abi=g.USDC_ABI)
        allow = usdc_ct.functions.allowance(acct.address, diamond).call()
        if allow < int(collateral * 1e6):
            lines.append("  approving USDC...")
            ap = usdc_ct.functions.approve(diamond, 2**255 - 1).build_transaction({
                "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": 70000, "gasPrice": w3.eth.gas_price})
            signed = acct.sign_transaction(ap)
            w3.eth.send_raw_transaction(signed.raw_transaction)
        trade_struct = {
            "user": acct.address, "index": 0, "pairIndex": pidx,
            "leverage": int(leverage * 1e3), "long": direction == "long", "isOpen": True,
            "collateralIndex": 1, "tradeType": 0,
            "collateralAmount": int(collateral * 1e6), "openPrice": int(px * 1e10),
            "tp": 0, "sl": int(sl_price * 1e10), "isCounterTrade": False,
            "positionSizeToken": 0, "__placeholder": 0,
        }
        tx_ct = w3.eth.contract(diamond, abi=g.TRADE_ABI)
        build = tx_ct.functions.openTrade(trade_struct, 30, "0x0000000000000000000000000000000000000000")
        try:
            gas = build.estimate_gas({"from": acct.address})
        except Exception as e:
            lines.append(f"  ❌ estimate failed: {str(e)[:200]}")
            print("\n".join(lines)); return
        tx = build.build_transaction({"from": acct.address,
                                      "nonce": w3.eth.get_transaction_count(acct.address),
                                      "gas": int(gas * 1.3), "gasPrice": w3.eth.gas_price})
        signed = acct.sign_transaction(tx)
        txh = w3.eth.send_raw_transaction(signed.raw_transaction)
        lines.append(f"  ✅ openTrade tx: {txh.hex()}")
        rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=180)
        ok = rcpt["status"] == 1
        lines.append(f"  status: {'SUCCESS' if ok else 'FAILED'}")
        if ok:
            lock_pct = lock_for_strength(strength)
            st["open"] = {"pair": pair, "direction": direction, "entry": px,
                          "tp": tp_price, "sl": sl_price, "ts": time.time(),
                          "tx": txh.hex(), "lock_pct": lock_pct, "strength": strength,
                          "collateral": collateral, "leverage": leverage}
            save_state(st)
            lock_label = "100% TP (confident)" if lock_pct >= 1.0 else f"{lock_pct*100:.0f}% profit-lock"
            lines.append(f"  intraday TP @ {tp_price:.2f} | SL @ {sl_price:.2f} (ATR-based) | lock: {lock_label}")
            notify_feishu(
                f"🟢 GAINS OPEN: {direction.upper()} {pair} ({interval}) @{px:.2f}\n"
                f"TP @ {tp_price:.2f} | SL @ {sl_price:.2f} | Strength {strength:.2f} | Lock {lock_label}\n"
                f"Collateral ${collateral:.2f} @{leverage}x | Notional ${collateral*leverage:.2f}")

    if lines:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
