#!/usr/bin/env python3
"""
gains_cycle_4h_sim.py — Simulate the ACTUAL cycle mode (daily signal, 4h execution)
to prove whether the 0.2% SL is the loss cause vs the signal.

Cycle mode reality: signal computed on DAILY PAXG close (SMA10+mom5), entry at the
next 4h bar, TP +0.3% / SL 0.2%. Test SL widths: 0.2% (current), 0.4%, 0.8%, 1.0xATR.
"""
import json, urllib.request, datetime
import numpy as np
import pandas as pd

def get_klines(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
    k = json.loads(urllib.request.urlopen(req, timeout=20).read())
    df = pd.DataFrame(k, columns=["t","o","h","l","c","v","ct","q","n","tb","tq","x"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df["open"] = df["o"].astype(float); df["high"] = df["h"].astype(float)
    df["low"] = df["l"].astype(float); df["close"] = df["c"].astype(float)
    return df[["date","open","high","low","close"]]

def main():
    daily = get_klines("PAXGUSDT", "1d", 250).tail(200).reset_index(drop=True)
    h4 = get_klines("PAXGUSDT", "4h", 1200)
    daily["sma10"] = daily["close"].rolling(10).mean()
    daily["mom5"] = daily["close"].pct_change(5)
    daily["signal"] = (daily["close"] > daily["sma10"]) & (daily["mom5"] > 0)

    # merge: for each 4h bar, use the most recent daily signal (as of that day's close)
    h4["day"] = h4["date"].dt.date
    daily["day"] = daily["date"].dt.date
    sig_map = dict(zip(daily["day"], daily["signal"]))
    # signal applies starting next day (daily close known at end of day)
    h4["signal"] = h4["day"].map(sig_map).shift(6)  # next day's first 4h bars

    # ATR on 4h
    tr = pd.concat([h4["high"]-h4["low"], (h4["high"]-h4["close"].shift()).abs(), (h4["low"]-h4["close"].shift()).abs()], axis=1).max(axis=1)
    h4["atr14"] = tr.rolling(14).mean()

    results = []
    for sl_name, sl_fn in [
        ("SL 0.20% (current)", lambda atr, px: px*0.002),
        ("SL 0.40%",           lambda atr, px: px*0.004),
        ("SL 0.80%",           lambda atr, px: px*0.008),
        ("SL 1.0xATR(4h)",     lambda atr, px: atr),
        ("SL 1.5xATR(4h)",     lambda atr, px: atr*1.5),
    ]:
        trades=0; wins=0; pnl=0.0; losses=0; timeouts=0
        max_hold = 6  # 24h max hold (6 x 4h bars)
        i = 0
        closes = h4["close"].values; highs = h4["high"].values; lows = h4["low"].values
        sig = h4["signal"].values; atrs = h4["atr14"].values
        while i < len(h4) - 1:
            if not (isinstance(sig[i], (bool, np.bool_)) and sig[i] and np.isfinite(atrs[i])):
                i += 1; continue
            entry = closes[i]
            sl_dist = sl_fn(atrs[i], entry)
            tp_price = entry * 1.003
            sl_price = entry - sl_dist
            outcome=None
            for j in range(i+1, min(i+1+max_hold, len(h4))):
                if highs[j] >= tp_price: outcome="win"; break
                if lows[j] <= sl_price: outcome="loss"; break
            if outcome is None:
                outcome="timeout"; 
            trades += 1
            if outcome=="win": wins += 1; pnl += 0.003
            elif outcome=="loss": losses += 1; pnl -= sl_dist/entry
            i += 1  # sequential scan (any signal bar)
        results.append((sl_name, trades, wins, losses, round(wins/max(trades,1)*100,1), round(pnl*100,2)))

    print("=== Daily-signal → 4h-execution sim (last ~200 days, LONG only) ===")
    print(f"{'SL config':18s} {'tr':>3s} {'W':>3s} {'L':>3s} {'WR%':>5s} {'PnL%':>7s}")
    for r in results:
        print(f"  {r[0]:16s} {r[1]:3d} {r[2]:3d} {r[3]:3d} {r[4]:5.1f} {r[5]:+7.2f}")

    print("\n=== The actual 3 losses — what gold did after entry ===")
    # entries from cron logs: Aug 7 00:01 @4233, 04:00 @4249, 08:01 @4248
    entries = [("Aug7 00:01", 4233.5), ("Aug7 04:00", 4249.3), ("Aug7 08:01", 4248.3)]
    h4f = h4[h4["date"] >= "2026-08-07"]
    for label, ep in entries:
        after = h4f[h4f["close"].shift(1) < ep] if False else h4f
        max_after = h4f["high"].max()
        min_after = h4f["low"].min()
        print(f"  {label}: entry ~{ep:.0f}, gold high after = {max_after:.0f} (+{(max_after/ep-1)*100:.2f}%), low = {min_after:.0f} ({(min_after/ep-1)*100:.2f}%)")

if __name__ == "__main__":
    main()
