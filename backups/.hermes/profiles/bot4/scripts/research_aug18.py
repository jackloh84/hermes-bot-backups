#!/usr/bin/env python3
"""research_aug18.py — fresh signal research for Limitless (bet) + Gains (invest).

Tests NEW signal ideas not in the Aug 9 grid:
  Limitless 5-min binary (WR is everything; fee breakeven 52.6%):
    bb_rsi        — Bollinger(20,2) + RSI(14) confluence (current champion, re-verify)
    rsi2          — RSI(2) extreme snap-back
    bb_rsi_vol    — Bollinger + RSI + volume spike (1.5x)
    stochastic    — Stochastic(14) <20 / >80
    wick          — hammer / shooting-star rejection candles
    vwap          — VWAP ± 1 std-dev mean reversion
  Gains 1h perp (return is everything):
    breakout      — 20-bar Donchian (current champion, re-verify)
    breakout_vol  — breakout + volume 1.5x confirmation
    breakout_2x   — breakout with wider 2.0 ATR take-profit
    ema_vol       — EMA20/50 cross + volume confirmation

Run: /home/ubuntu/venv/bin/python3 research_aug18.py [--days 120]
"""
import sys, time, json, argparse, math
sys.path.insert(0, "/home/ubuntu/.hermes/profiles/bot4/scripts")
import trading_engine as te


# ---------------- NEW signals (Limitless binary) ----------------
def sig_rsi2(bars):
    closes = [b["c"] for b in bars]
    r = te.rsi(closes, 2)
    s = [0] * len(bars)
    for i in range(1, len(bars)):
        if r[i] < 10 and r[i - 1] >= 10:
            s[i] = 1
        elif r[i] > 90 and r[i - 1] <= 90:
            s[i] = -1
    return s


def sig_bb_rsi(bars):
    closes = [b["c"] for b in bars]
    _, up, lo = te.bollinger(closes, 20, 2.0)
    r = te.rsi(closes, 14)
    s = [0] * len(bars)
    for i in range(30, len(bars)):
        if closes[i] < lo[i] and r[i] < 30:
            s[i] = 1
        elif closes[i] > up[i] and r[i] > 70:
            s[i] = -1
    return s


def sig_bb_rsi_vol(bars):
    closes = [b["c"] for b in bars]
    _, up, lo = te.bollinger(closes, 20, 2.0)
    r = te.rsi(closes, 14)
    vols = [b["v"] for b in bars]
    s = [0] * len(bars)
    for i in range(30, len(bars)):
        va = sum(vols[i - 20:i]) / 20
        spike = vols[i] > 1.5 * va
        if closes[i] < lo[i] and r[i] < 30 and spike:
            s[i] = 1
        elif closes[i] > up[i] and r[i] > 70 and spike:
            s[i] = -1
    return s


def sig_stochastic(bars, k=14):
    closes = [b["c"] for b in bars]
    s = [0] * len(bars)
    for i in range(k, len(bars)):
        hh = max(b["h"] for b in bars[i - k + 1:i + 1])
        ll = min(b["l"] for b in bars[i - k + 1:i + 1])
        if hh == ll:
            continue
        kk = (closes[i] - ll) / (hh - ll) * 100
        if kk < 20:
            s[i] = 1
        elif kk > 80:
            s[i] = -1
    return s


def sig_wick(bars):
    s = [0] * len(bars)
    for i in range(2, len(bars)):
        b = bars[i]
        rng = b["h"] - b["l"]
        if rng == 0:
            continue
        body = abs(b["c"] - b["o"])
        low_wick = min(b["o"], b["c"]) - b["l"]
        up_wick = b["h"] - max(b["o"], b["c"])
        prev_dn = bars[i - 1]["c"] < bars[i - 2]["c"]
        prev_up = bars[i - 1]["c"] > bars[i - 2]["c"]
        if low_wick > 1.5 * body and low_wick > 0.4 * rng and prev_dn:
            s[i] = 1
        elif up_wick > 1.5 * body and up_wick > 0.4 * rng and prev_up:
            s[i] = -1
    return s


def sig_vwap(bars):
    s = [0] * len(bars)
    cum_pv = cum_v = 0.0
    for i in range(len(bars)):
        b = bars[i]
        typ = (b["h"] + b["l"] + b["c"]) / 3
        cum_pv += typ * b["v"]
        cum_v += b["v"]
        vwap = cum_pv / cum_v if cum_v else b["c"]
        if i >= 20:
            win = bars[i - 20:i + 1]
            types = [(x["h"] + x["l"] + x["c"]) / 3 for x in win]
            m = sum(types) / len(types)
            sd = (sum((t - m) ** 2 for t in types) / len(types)) ** 0.5
            if b["c"] < vwap - sd:
                s[i] = 1
            elif b["c"] > vwap + sd:
                s[i] = -1
    return s


# ---------------- NEW signals (Gains 1h perp) ----------------
def sig_breakout_vol(bars, n=20, mult=1.5):
    vols = [b["v"] for b in bars]
    s = [0] * len(bars)
    for i in range(30, len(bars)):
        hh = max(b["h"] for b in bars[i - n:i])
        ll = min(b["l"] for b in bars[i - n:i])
        va = sum(vols[i - 20:i]) / 20
        if bars[i]["c"] > hh and vols[i] > mult * va:
            s[i] = 1
        elif bars[i]["c"] < ll and vols[i] > mult * va:
            s[i] = -1
    return s


def sig_ema_vol(bars):
    closes = [b["c"] for b in bars]
    f, s50 = te.ema(closes, 20), te.ema(closes, 50)
    vols = [b["v"] for b in bars]
    s = [0] * len(bars)
    for i in range(1, len(bars)):
        va = sum(vols[max(0, i - 20):i]) / max(1, min(20, i))
        spike = vols[i] > 1.3 * va
        if f[i] > s50[i] and f[i - 1] <= s50[i - 1] and spike:
            s[i] = 1
        elif f[i] < s50[i] and f[i - 1] >= s50[i - 1] and spike:
            s[i] = -1
    return s


# ---------------- backtest helpers ----------------
def bt_binary(bars, sig, fee=3.0, settle=1):
    closes = [b["c"] for b in bars]
    wins = losses = 0
    for i in range(len(bars) - settle):
        if sig[i] == 0:
            continue
        w = (sig[i] == 1 and closes[i + settle] > closes[i]) or \
            (sig[i] == -1 and closes[i + settle] < closes[i])
        if w:
            wins += 1
        else:
            losses += 1
    n = wins + losses
    if n == 0:
        return {"n": 0, "wr": 0.0, "exp": 0.0}
    wr = wins / n * 100
    exp = wr / 100 * (1 - fee / 100) - (1 - wr / 100) * 1.0  # win +0.97, lose -1.0
    return {"n": n, "wr": round(wr, 1), "exp": round(exp * 100, 2)}


def bt_perp(bars, sig, fee=0.10, tp_atr=1.5, sl_atr=1.0):
    atrs = te.atr(bars, 14)
    eq = 1.0
    pos = 0
    entry = tp = sl = 0.0
    for i in range(1, len(bars)):
        px = bars[i]["c"]
        if pos != 0:
            hit = (px >= tp) if pos == 1 else (px <= tp)
            hit_sl = (px <= sl) if pos == 1 else (px >= sl)
            if hit or hit_sl:
                pnl = ((px - entry) / entry - fee / 100) if pos == 1 else ((entry - px) / entry - fee / 100)
                eq *= (1 + pnl)
                pos = 0
                continue
        if pos == 0 and sig[i] != 0:
            pos = sig[i]
            entry = px
            a = atrs[i] if not math.isnan(atrs[i]) else px * 0.003
            if pos == 1:
                tp = entry * (1 + tp_atr * a / entry)
                sl = entry * (1 - sl_atr * a / entry)
            else:
                tp = entry * (1 - tp_atr * a / entry)
                sl = entry * (1 + sl_atr * a / entry)
    return round((eq - 1) * 100, 1)


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    args = ap.parse_args()

    print(f"=== Limitless 5-min binary — win-rate research ({args.days} days) ===\n")
    lml_sigs = {"bb_rsi": sig_bb_rsi, "rsi2": sig_rsi2, "bb_rsi_vol": sig_bb_rsi_vol,
                "stochastic": sig_stochastic, "wick": sig_wick, "vwap": sig_vwap}
    rows = []
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        bars = te.fetch_klines(sym, "5m", args.days)
        print(f"  {sym}: {len(bars)} candles", file=sys.stderr)
        for name, fn in lml_sigs.items():
            sig = fn(bars)
            r = bt_binary(bars, sig)
            r.update({"sym": sym, "name": name})
            rows.append(r)
    print(f"{'sym':<10}{'signal':<14}{'n':>6}{'WR%':>8}{'exp%':>8}")
    for r in sorted(rows, key=lambda x: -x["wr"]):
        mark = " << edge" if r["wr"] > 53.5 and r["exp"] > 0 else ""
        print(f"{r['sym']:<10}{r['name']:<14}{r['n']:>6}{r['wr']:>8}{r['exp']:>8}{mark}")

    print(f"\n=== Gains 1h perp — return research ({args.days} days) ===\n")
    gains_sigs = {"breakout": ("breakout", 1.5, 1.0), "breakout_vol": ("breakout_vol", 1.5, 1.0),
                  "breakout_2x": ("breakout", 2.0, 1.0), "ema_vol": ("ema_vol", 1.5, 1.0)}
    grows = []
    for sym in ["BTCUSDT", "ETHUSDT"]:
        bars = te.fetch_klines(sym, "1h", args.days)
        print(f"  {sym}: {len(bars)} candles", file=sys.stderr)
        for name, (strat, tp, sl) in gains_sigs.items():
            if strat == "breakout":
                sig = te.signals_for(bars, "breakout")
            elif strat == "breakout_vol":
                sig = sig_breakout_vol(bars)
            else:
                sig = sig_ema_vol(bars)
            ret = bt_perp(bars, sig, 0.10, tp, sl)
            grows.append({"sym": sym, "name": name, "ret": ret})
    print(f"{'sym':<10}{'signal':<14}{'ret%':>8}")
    for r in sorted(grows, key=lambda x: -x["ret"]):
        mark = " << best" if r["ret"] > 10 else ""
        print(f"{r['sym']:<10}{r['name']:<14}{r['ret']:>8}{mark}")

    out = "/home/ubuntu/research_aug18_results.json"
    json.dump({"limitless": rows, "gains": grows}, open(out, "w"), indent=1)
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()
