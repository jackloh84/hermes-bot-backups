#!/usr/bin/env python3
"""
backtest_unified.py — ONE backtest engine for ALL Jack's lanes (Aug 9 2026).

Lanes supported (same script, lane selects the mechanics):
  --lane gains      : Gains gTrade perps — long/short with ATR TP/SL (1h/30m data)
  --lane hyperliquid: Hyperliquid perps — identical mechanics to Gains (BTC/ETH 1h)
  --lane limitless  : Limitless 5-min up/down binary — signal -> settle N min later,
                      win/lose on direction (raw signal accuracy + EV @0.50 entry)

Strategies (identical code for every lane):
  rsi           : RSI(14) mean-reversion (oversold buy / overbought short)
  ema_cross     : EMA 20/50 cross (trend)
  ema_momentum  : close vs EMA20 + 3-bar momentum (the ORIGINAL Gains signal)
  bollinger     : Bollinger(20,2) mean-reversion (touch lower/upper band)
  breakout      : 20-bar Donchian breakout (trend)

Data: Binance klines, paginated — 6+ months via startTime paging (1000/page).
Output: win rate, trades, return, avg win/loss — same table for every lane.

Usage:
  python3 backtest_unified.py --lane gains --days 180
  python3 backtest_unified.py --lane limitless --days 180
  python3 backtest_unified.py --lane hyperliquid --days 180 --strategies rsi,bollinger
  python3 backtest_unified.py --all            # run every lane, save JSON + summary
"""
import argparse, datetime, json, math, os, sys, time, urllib.request

LANE_DEFAULTS = {
    "gains":       {"symbols": ["BTCUSDT", "ETHUSDT", "PAXGUSDT"], "interval": "1h",
                    "fee_pct": 0.10, "tp_atr": 1.5, "sl_atr": 1.0},
    "hyperliquid": {"symbols": ["BTCUSDT", "ETHUSDT"],            "interval": "1h",
                    "fee_pct": 0.02, "tp_atr": 1.5, "sl_atr": 1.0},
    "limitless":   {"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"], "interval": "5m",
                    "fee_pct": 3.0,  "settle_bars": 1},  # buy, settle 1 bar (5 min) later
}

STRATEGIES = ["rsi", "ema_cross", "ema_momentum", "bollinger", "breakout"]

OUT = "/home/ubuntu/backtest_unified_results.json"


def fetch_klines(symbol, interval, days):
    """Paginate Binance klines backward from now until `days` covered."""
    all_rows = []
    end_ms = int(time.time() * 1000)
    per_page = 1000
    pages = max(1, math.ceil(days * 86400 * 1000 / (per_page * _ms_per_bar(interval))))
    for p in range(pages):
        start = end_ms - (p + 1) * per_page * _ms_per_bar(interval)
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
               f"&interval={interval}&limit={per_page}&startTime={int(start)}&endTime={end_ms - p*per_page*_ms_per_bar(interval)}")
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
        try:
            k = json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            break
        if not k:
            break
        for r in k:
            all_rows.append({
                "t": r[0], "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
                "c": float(r[4]), "v": float(r[5]),
            })
        time.sleep(0.15)
    all_rows.sort(key=lambda x: x["t"])
    # dedupe by timestamp
    seen, out = set(), []
    for r in all_rows:
        if r["t"] not in seen:
            seen.add(r["t"])
            out.append(r)
    return out


def _ms_per_bar(interval):
    unit = interval[-1]
    n = int(interval[:-1]) if len(interval) > 1 else 1
    mult = {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 60000)
    return n * mult


def ema(vals, n):
    k = 2 / (n + 1)
    e = vals[0]
    out = [e]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def rsi(vals, n=14):
    out = [50.0] * len(vals)
    for i in range(n, len(vals)):
        gains = losses = 0.0
        for j in range(i - n + 1, i + 1):
            d = vals[j] - vals[j - 1]
            if d > 0:
                gains += d
            else:
                losses -= d
        if losses == 0:
            out[i] = 100.0
        else:
            rs = (gains / n) / (losses / n)
            out[i] = 100 - 100 / (1 + rs)
    return out


def bollinger(closes, n=20, mult=2.0):
    mid, up, lo = [], [], []
    for i in range(len(closes)):
        if i < n - 1:
            mid.append(closes[i]); up.append(closes[i]); lo.append(closes[i])
            continue
        window = closes[i - n + 1:i + 1]
        m = sum(window) / n
        var = sum((x - m) ** 2 for x in window) / n
        sd = var ** 0.5
        mid.append(m); up.append(m + mult * sd); lo.append(m - mult * sd)
    return mid, up, lo


def atr(bars, n=14):
    out = [float("nan")] * len(bars)
    trs = []
    for i in range(1, len(bars)):
        trs.append(max(bars[i]["h"] - bars[i]["l"],
                       abs(bars[i]["h"] - bars[i - 1]["c"]),
                       abs(bars[i]["l"] - bars[i - 1]["c"])))
    for i in range(n, len(bars)):
        out[i] = sum(trs[i - n:i]) / n
    return out


def signals_for(bars, strat):
    """Compute per-bar signal: +1 long, -1 short, 0 flat."""
    closes = [b["c"] for b in bars]
    sig = [0] * len(bars)
    if strat == "ema_cross":
        f = ema(closes, 20); s = ema(closes, 50)
        for i in range(1, len(bars)):
            if f[i] > s[i] and f[i - 1] <= s[i - 1]:
                sig[i] = 1
            elif f[i] < s[i] and f[i - 1] >= s[i - 1]:
                sig[i] = -1
    elif strat == "ema_momentum":
        e = ema(closes, 20)
        for i in range(4, len(bars)):
            mom = (closes[i] - closes[i - 3]) / closes[i - 3]
            if closes[i] > e[i] and mom > 0:
                sig[i] = 1
            elif closes[i] < e[i] and mom < 0:
                sig[i] = -1
    elif strat == "rsi":
        r = rsi(closes, 14)
        for i in range(1, len(bars)):
            if r[i] < 30 and r[i - 1] >= 30:
                sig[i] = 1
            elif r[i] > 70 and r[i - 1] <= 70:
                sig[i] = -1
    elif strat == "bollinger":
        _, up, lo = bollinger(closes, 20, 2.0)
        for i in range(1, len(bars)):
            if closes[i] < lo[i] and closes[i - 1] >= lo[i - 1]:
                sig[i] = 1
            elif closes[i] > up[i] and closes[i - 1] <= up[i - 1]:
                sig[i] = -1
    elif strat == "breakout":
        for i in range(21, len(bars)):
            hh = max(b["h"] for b in bars[i - 20:i])
            ll = min(b["l"] for b in bars[i - 20:i])
            if closes[i] > hh:
                sig[i] = 1
            elif closes[i] < ll:
                sig[i] = -1
    return sig


def backtest_perp(bars, sig, fee_pct, tp_atr, sl_atr):
    """Long/short with ATR TP/SL. Returns stats dict."""
    atrs = atr(bars, 14)
    trades = []
    pos = 0          # 0 flat, 1 long, -1 short
    entry = 0.0
    tp = sl = 0.0
    eq = 1.0
    for i in range(1, len(bars)):
        px = bars[i]["c"]
        if pos != 0:
            # check TP/SL
            if pos == 1:
                pnl_pct = (px - entry) / entry - fee_pct / 100
                hit_tp = px >= tp; hit_sl = px <= sl
            else:
                pnl_pct = (entry - px) / entry - fee_pct / 100
                hit_tp = px <= tp; hit_sl = px >= sl
            if hit_tp or hit_sl:
                trades.append(pnl_pct)
                eq *= (1 + pnl_pct)
                pos = 0
                continue
        if pos == 0 and sig[i] != 0:
            pos = sig[i]
            entry = px
            a = atrs[i] if i < len(atrs) and not math.isnan(atrs[i]) else px * 0.003
            if pos == 1:
                tp = entry * (1 + tp_atr * a / entry)
                sl = entry * (1 - sl_atr * a / entry)
            else:
                tp = entry * (1 - tp_atr * a / entry)
                sl = entry * (1 + sl_atr * a / entry)
    return _stats(trades, eq)


def backtest_binary(bars, sig, fee_pct, settle_bars):
    """Limitless-style: signal -> buy token at entry, settle N bars later.
    Raw directional accuracy + EV at fair 0.50 entry."""
    closes = [b["c"] for b in bars]
    trades = []
    eq = 1.0
    for i in range(len(bars) - settle_bars):
        if sig[i] == 0:
            continue
        entry = closes[i]
        settle = closes[i + settle_bars]
        win = (sig[i] == 1 and settle > entry) or (sig[i] == -1 and settle < entry)
        # fair-entry EV: pay 0.50, win pays 1.0; fee 3% on entry
        pnl_pct = 1.0 - fee_pct / 100 if win else -1.0  # double stake or lose it
        trades.append(pnl_pct)
        eq *= (1 + pnl_pct)
    return _stats(trades, eq)


def _stats(trades, eq):
    if not trades:
        return {"trades": 0, "wr": 0.0, "ret": 0.0, "avgW": 0.0, "avgL": 0.0}
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    wr = len(wins) / len(trades) * 100
    return {
        "trades": len(trades),
        "wr": round(wr, 1),
        "ret": round((eq - 1) * 100, 1),
        "avgW": round(sum(wins) / len(wins) * 100, 2) if wins else 0.0,
        "avgL": round(sum(losses) / len(losses) * 100, 2) if losses else 0.0,
    }


def run_lane(lane, days, strategies):
    cfg = LANE_DEFAULTS[lane]
    results = []
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=list(LANE_DEFAULTS.keys()) + ["all"])
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--strategies", default=",".join(STRATEGIES))
    args = ap.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    lanes = list(LANE_DEFAULTS.keys()) if args.lane == "all" else [args.lane]

    print(f"BACKTEST UNIFIED — {args.days} days | strategies: {strategies}")
    print(f"lanes: {lanes}\n")
    all_res = []
    for lane in lanes:
        print(f"### LANE: {lane}")
        all_res += run_lane(lane, args.days, strategies)

    print("\n" + "=" * 100)
    print("SUMMARY — win rate per (lane, symbol, strategy)")
    print("=" * 100)
    for r in sorted(all_res, key=lambda x: (-x["wr"], x["trades"])):
        print(f"{r['lane']:<12} {r['symbol']:<10} {r['strategy']:<14} WR={r['wr']:5.1f}%  n={r['trades']:3d}  ret={r['ret']:+6.1f}%  avgW={r['avgW']:+.1f}% avgL={r['avgL']:+.1f}%")
    json.dump(all_res, open(OUT, "w"), indent=1)
    print(f"\nsaved: {OUT}")


if __name__ == "__main__":
    main()
