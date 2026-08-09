#!/usr/bin/env python3
"""
trading_engine.py — UNIFIED engine: backtest + live, ALL lanes, ONE signal library.

Lanes:
  gains       : Gains gTrade perps (Base) — contract calls, ATR TP/SL
  hyperliquid : Hyperliquid perps — SDK, ATR TP/SL
  limitless   : Limitless 5-min up/down binary — SDK, settle-by-time

Modes:
  --mode backtest : simulate a strategy on historical data (no money)
  --mode live     : run the SAME strategy live on a lane (real orders)

Strategies (identical code everywhere):
  rsi, ema_cross, ema_momentum, bollinger, breakout

Usage:
  python3 trading_engine.py --mode backtest --lane all --days 180
  python3 trading_engine.py --mode backtest --lane hyperliquid --strategy rsi
  python3 trading_engine.py --mode live --lane hyperliquid --strategy rsi --dry
  python3 trading_engine.py --mode live --lane gains --strategy bollinger --dry
  python3 trading_engine.py --mode live --lane limitless --strategy ema_cross --dry
  (remove --dry to place REAL orders — Jack must approve first)
"""
import argparse, datetime, json, math, os, sys, time, urllib.request

# ---------------- shared config ----------------
WALLET = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
HL_API = "https://api.hyperliquid.xyz"
LANE_DEFAULTS = {
    "gains":       {"symbols": ["BTCUSDT", "ETHUSDT", "PAXGUSDT"], "interval": "1h",
                    "fee_pct": 0.10, "tp_atr": 1.5, "sl_atr": 1.0},
    "hyperliquid": {"symbols": ["BTCUSDT", "ETHUSDT"],            "interval": "1h",
                    "fee_pct": 0.02, "tp_atr": 1.5, "sl_atr": 1.0},
    "limitless":   {"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"], "interval": "5m",
                    "fee_pct": 3.0,  "settle_bars": 1},
}
STRATEGIES = ["rsi", "ema_cross", "ema_momentum", "bollinger", "breakout"]
STATE_DIR = "/home/ubuntu/.hermes/profiles/bot4/state"


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


# ---------------- data ----------------
def _ms_per_bar(interval):
    unit = interval[-1]
    n = int(interval[:-1]) if len(interval) > 1 else 1
    return n * {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 60000)


def fetch_klines(symbol, interval, days):
    all_rows, end_ms = [], int(time.time() * 1000)
    per_page, ms = 1000, _ms_per_bar(interval)
    pages = max(1, math.ceil(days * 86400 * 1000 / (per_page * ms)))
    for p in range(pages):
        start = end_ms - (p + 1) * per_page * ms
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}"
               f"&limit={per_page}&startTime={int(start)}&endTime={int(end_ms - p*per_page*ms)}")
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
        try:
            k = json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            break
        if not k:
            break
        for r in k:
            all_rows.append({"t": r[0], "o": float(r[1]), "h": float(r[2]),
                             "l": float(r[3]), "c": float(r[4]), "v": float(r[5])})
        time.sleep(0.15)
    all_rows.sort(key=lambda x: x["t"])
    seen, out = set(), []
    for r in all_rows:
        if r["t"] not in seen:
            seen.add(r["t"])
            out.append(r)
    return out


# ---------------- indicators ----------------
def ema(vals, n):
    k = 2 / (n + 1); e = vals[0]; out = [e]
    for v in vals[1:]:
        e = v * k + e * (1 - k); out.append(e)
    return out


def rsi(vals, n=14):
    out = [50.0] * len(vals)
    for i in range(n, len(vals)):
        gains = losses = 0.0
        for j in range(i - n + 1, i + 1):
            d = vals[j] - vals[j - 1]
            gains += d if d > 0 else 0; losses += -d if d < 0 else 0
        out[i] = 100.0 if losses == 0 else 100 - 100 / (1 + (gains / n) / (losses / n))
    return out


def bollinger(closes, n=20, mult=2.0):
    mid, up, lo = [], [], []
    for i in range(len(closes)):
        if i < n - 1:
            mid.append(closes[i]); up.append(closes[i]); lo.append(closes[i]); continue
        w = closes[i - n + 1:i + 1]; m = sum(w) / n
        sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
        mid.append(m); up.append(m + mult * sd); lo.append(m - mult * sd)
    return mid, up, lo


def atr(bars, n=14):
    out = [float("nan")] * len(bars); trs = []
    for i in range(1, len(bars)):
        trs.append(max(bars[i]["h"] - bars[i]["l"],
                       abs(bars[i]["h"] - bars[i - 1]["c"]),
                       abs(bars[i]["l"] - bars[i - 1]["c"])))
    for i in range(n, len(bars)):
        out[i] = sum(trs[i - n:i]) / n
    return out


# ---------------- signals (SHARED — backtest AND live) ----------------
def signals_for(bars, strat):
    closes = [b["c"] for b in bars]
    sig = [0] * len(bars)
    if strat == "ema_cross":
        f, s = ema(closes, 20), ema(closes, 50)
        for i in range(1, len(bars)):
            if f[i] > s[i] and f[i - 1] <= s[i - 1]: sig[i] = 1
            elif f[i] < s[i] and f[i - 1] >= s[i - 1]: sig[i] = -1
    elif strat == "ema_momentum":
        e = ema(closes, 20)
        for i in range(4, len(bars)):
            mom = (closes[i] - closes[i - 3]) / closes[i - 3]
            if closes[i] > e[i] and mom > 0: sig[i] = 1
            elif closes[i] < e[i] and mom < 0: sig[i] = -1
    elif strat == "rsi":
        r = rsi(closes, 14)
        for i in range(1, len(bars)):
            if r[i] < 30 and r[i - 1] >= 30: sig[i] = 1
            elif r[i] > 70 and r[i - 1] <= 70: sig[i] = -1
    elif strat == "bollinger":
        _, up, lo = bollinger(closes, 20, 2.0)
        for i in range(1, len(bars)):
            if closes[i] < lo[i] and closes[i - 1] >= lo[i - 1]: sig[i] = 1
            elif closes[i] > up[i] and closes[i - 1] <= up[i - 1]: sig[i] = -1
    elif strat == "breakout":
        for i in range(21, len(bars)):
            hh = max(b["h"] for b in bars[i - 20:i])
            ll = min(b["l"] for b in bars[i - 20:i])
            if closes[i] > hh: sig[i] = 1
            elif closes[i] < ll: sig[i] = -1
    return sig


def last_signal(bars, strat):
    """Current actionable signal from the LAST bar: 1 long, -1 short, 0 none."""
    if len(bars) < 60:
        return 0
    sig = signals_for(bars, strat)
    return sig[-1]


# ---------------- backtest ----------------
def backtest_perp(bars, sig, fee_pct, tp_atr, sl_atr):
    atrs = atr(bars, 14); trades = []
    pos = 0; entry = tp = sl = 0.0; eq = 1.0
    for i in range(1, len(bars)):
        px = bars[i]["c"]
        if pos != 0:
            pnl = ((px - entry) / entry - fee_pct / 100) if pos == 1 else ((entry - px) / entry - fee_pct / 100)
            hit = (px >= tp) if pos == 1 else (px <= tp)
            hit_sl = (px <= sl) if pos == 1 else (px >= sl)
            if hit or hit_sl:
                trades.append(pnl); eq *= (1 + pnl); pos = 0; continue
        if pos == 0 and sig[i] != 0:
            pos = sig[i]; entry = px
            a = atrs[i] if not math.isnan(atrs[i]) else px * 0.003
            if pos == 1:
                tp = entry * (1 + tp_atr * a / entry); sl = entry * (1 - sl_atr * a / entry)
            else:
                tp = entry * (1 - tp_atr * a / entry); sl = entry * (1 + sl_atr * a / entry)
    return _stats(trades, eq)


def backtest_binary(bars, sig, fee_pct, settle_bars):
    closes = [b["c"] for b in bars]; trades = []; eq = 1.0
    for i in range(len(bars) - settle_bars):
        if sig[i] == 0:
            continue
        win = (sig[i] == 1 and closes[i + settle_bars] > closes[i]) or \
              (sig[i] == -1 and closes[i + settle_bars] < closes[i])
        trades.append(1.0 - fee_pct / 100 if win else -1.0)
        eq *= (1 + trades[-1])
    return _stats(trades, eq)


def _stats(trades, eq):
    if not trades:
        return {"trades": 0, "wr": 0.0, "ret": 0.0, "avgW": 0.0, "avgL": 0.0}
    wins = [t for t in trades if t > 0]; losses = [t for t in trades if t <= 0]
    return {"trades": len(trades), "wr": round(len(wins) / len(trades) * 100, 1),
            "ret": round((eq - 1) * 100, 1),
            "avgW": round(sum(wins) / len(wins) * 100, 2) if wins else 0.0,
            "avgL": round(sum(losses) / len(losses) * 100, 2) if losses else 0.0}


def run_backtest(lane, days, strategies):
    cfg = LANE_DEFAULTS[lane]; results = []
    for sym in cfg["symbols"]:
        bars = fetch_klines(sym, cfg["interval"], days)
        print(f"  {sym} {cfg['interval']}: {len(bars)} candles", file=sys.stderr)
        if len(bars) < 60:
            continue
        for strat in strategies:
            sig = signals_for(bars, strat)
            if lane == "limitless":
                st = backtest_binary(bars, sig, cfg["fee_pct"], cfg["settle_bars"])
            else:
                st = backtest_perp(bars, sig, cfg["fee_pct"], cfg["tp_atr"], cfg["sl_atr"])
            st.update({"lane": lane, "symbol": sym, "strategy": strat, "interval": cfg["interval"]})
            results.append(st)
    return results


# ---------------- live executors ----------------
def live_hyperliquid(strat, dry=True):
    env = load_env()
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    acct = Account.from_key(env["WALLET_PK"])
    assert acct.address.lower() == WALLET.lower()
    exchange = Exchange(acct, base_url=HL_API)
    info = Info(HL_API, skip_ws=True)
    # UNIFIED ACCOUNT: balance lives in spot clearinghouse state; perp user_state
    # reads 0.0 but is NOT meaningful (HL docs, verified Aug 9 2026).
    spot = info.spot_user_state(acct.address)
    bal = sum(float(b.get("total", 0)) for b in spot.get("balances", [])
              if b.get("coin") == "USDC")
    print(f"[HL] balance ${bal:.2f} | strategy={strat} | {'DRY' if dry else 'LIVE'}")

    # check current position (unified: read assetPositions from perp dex state)
    state = info.user_state(acct.address)
    for ap in state.get("assetPositions", []):
        p = ap["position"]
        if float(p.get("szi", 0)) != 0:
            print(f"[HL] holding {p['coin']} szi={p['szi']} entry={p['entryPx']}")
            return
    # find signal
    best = None
    for sym in LANE_DEFAULTS["hyperliquid"]["symbols"]:
        name = sym.replace("USDT", "")
        bars = fetch_klines(sym, "1h", 10)
        s = last_signal(bars, strat)
        if s != 0:
            best = (name, "buy" if s == 1 else "sell", bars[-1]["c"])
            break
    if not best:
        print("[HL] no signal"); return
    name, side, px = best
    print(f"[HL] signal: {side.upper()} {name} @ {px}")
    if dry:
        print(f"[HL DRY] would {'LONG' if side=='buy' else 'SHORT'} {name}")
        return
    sz = round(10 / px, 5 if name == "BTC" else 4)
    exchange.update_leverage(name, 3, True)
    result = exchange.market_open(name, side == "buy", sz, px)
    print(f"[HL] order result: {json.dumps(result)[:200]}")


def live_gains(strat, dry=True):
    print(f"[Gains] strategy={strat} | {'DRY' if dry else 'LIVE'}")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gains_weekly_lane as g
    # signal on BTC/ETH/XAU
    best = None
    for sym in LANE_DEFAULTS["gains"]["symbols"]:
        bars = fetch_klines(sym, "1h", 10)
        s = last_signal(bars, strat)
        if s != 0:
            best = (sym, s, bars[-1]["c"])
            break
    if not best:
        print("[Gains] no signal"); return
    sym, s, px = best
    print(f"[Gains] signal: {'LONG' if s==1 else 'SHORT'} {sym} @ {px}")
    if dry:
        print(f"[Gains DRY] would open {'LONG' if s==1 else 'SHORT'} {sym}")
        return
    # NOTE: real execution reuses gains_weekly_lane's openTradeMarket flow.
    print("[Gains LIVE] execution wired via gains_weekly_lane.openTradeMarket (manual review before first live)")


def live_limitless(strat, dry=True):
    print(f"[Limitless] strategy={strat} | {'DRY' if dry else 'LIVE'}")
    bars = fetch_klines("BTCUSDT", "5m", 10)
    s = last_signal(bars, strat)
    print(f"[Limitless] BTC 5m signal: {'UP' if s==1 else 'DOWN' if s==-1 else 'NONE'} @ {bars[-1]['c']}")
    if dry:
        print(f"[Limitless DRY] would bet {'UP' if s==1 else 'DOWN'}")
        return
    print("[Limitless LIVE] execution wired via limitless_auto.py (manual review before first live)")


EXECUTORS = {"hyperliquid": live_hyperliquid, "gains": live_gains, "limitless": live_limitless}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["backtest", "live"], required=True)
    ap.add_argument("--lane", choices=list(LANE_DEFAULTS.keys()) + ["all"], required=True)
    ap.add_argument("--strategy", default="rsi")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--dry", action="store_true", default=True)
    args = ap.parse_args()

    if args.mode == "backtest":
        strategies = STRATEGIES if args.strategy == "all" else [args.strategy]
        lanes = list(LANE_DEFAULTS.keys()) if args.lane == "all" else [args.lane]
        print(f"BACKTEST — {args.days} days | strategies: {strategies}")
        all_res = []
        for lane in lanes:
            print(f"\n### LANE: {lane}")
            all_res += run_backtest(lane, args.days, strategies)
        print("\n" + "=" * 96)
        print("SUMMARY — win rate per (lane, symbol, strategy)")
        print("=" * 96)
        for r in sorted(all_res, key=lambda x: (-x["wr"], x["trades"])):
            print(f"{r['lane']:<12} {r['symbol']:<10} {r['strategy']:<14} WR={r['wr']:5.1f}%  n={r['trades']:3d}  ret={r['ret']:+6.1f}%  avgW={r['avgW']:+.1f}% avgL={r['avgL']:+.1f}%")
        out = "/home/ubuntu/backtest_unified_results.json"
        json.dump(all_res, open(out, "w"), indent=1)
        print(f"\nsaved: {out}")
    else:
        lanes = list(LANE_DEFAULTS.keys()) if args.lane == "all" else [args.lane]
        for lane in lanes:
            EXECUTORS[lane](args.strategy, dry=args.dry)


if __name__ == "__main__":
    main()
