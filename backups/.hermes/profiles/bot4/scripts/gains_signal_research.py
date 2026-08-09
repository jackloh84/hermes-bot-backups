#!/usr/bin/env python3
"""
gains_signal_research.py — Backtest stronger signals for the Gains XAU/USD cycle lane.

Research question: 3 consecutive LONG XAU trades all hit the 0.2% SL while gold
then rallied +1.25%. Is the signal wrong, or is the trade management (TP/SL)
wrong? Test signal variants + wider ATR-based stops on real PAXG history.

Uses free Binance PAXGUSDT klines (gold proxy, tracks XAU within ~$1).
"""
import json, urllib.request, datetime
import numpy as np
import pandas as pd

def get_klines(symbol="PAXGUSDT", interval="1d", limit=400):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
    k = json.loads(urllib.request.urlopen(req, timeout=20).read())
    df = pd.DataFrame(k, columns=["t","o","h","l","c","v","ct","q","n","tb","tq","x"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df["open"] = df["o"].astype(float); df["high"] = df["h"].astype(float)
    df["low"] = df["l"].astype(float); df["close"] = df["c"].astype(float)
    df["volume"] = df["v"].astype(float)
    return df[["date","open","high","low","close","volume"]]

def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)
def atr(df, n=14):
    tr = pd.concat([df["high"]-df["low"], (df["high"]-df["close"].shift()).abs(), (df["low"]-df["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def backtest(df, signal_col, direction_col, tp_pct, sl_pct, max_hold=5, name="", atr_stop=False):
    """Simulate: enter on signal, TP/SL price levels, hold up to max_hold bars."""
    trades = 0; wins = 0; pnl = 0.0; pnl_pct_list = []
    i = 0
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    dates = df["date"].values
    sig = signal_col.values
    direc = direction_col.values
    atr_vals = df["atr"].values if "atr" in df else None
    while i < len(df) - 1:
        d = direc[i]
        if d is None or not np.isfinite(d) or pd.isna(sig[i]):
            i += 1; continue
        entry = closes[i]
        if atr_stop and atr_vals is not None and np.isfinite(atr_vals[i]):
            # ATR-based stop: 1.0 x ATR(14) away; TP 1.5 x ATR
            sl_dist = atr_vals[i]
            tp_dist = atr_vals[i] * 1.5
            sl_price = entry - sl_dist if d == 1 else entry + sl_dist
            tp_price = entry + tp_dist if d == 1 else entry - tp_dist
        else:
            sl_price = entry * (1 - sl_pct) if d == 1 else entry * (1 + sl_pct)
            tp_price = entry * (1 + tp_pct) if d == 1 else entry * (1 - tp_pct)
        # walk forward up to max_hold bars
        outcome = None; exit_price = None
        for j in range(i+1, min(i+1+max_hold, len(df))):
            hi, lo = highs[j], lows[j]
            if d == 1:
                if hi >= tp_price:
                    outcome = "win"; exit_price = tp_price; break
                if lo <= sl_price:
                    outcome = "loss"; exit_price = sl_price; break
            else:
                if lo <= tp_price:
                    outcome = "win"; exit_price = tp_price; break
                if hi >= sl_price:
                    outcome = "loss"; exit_price = sl_price; break
        if outcome is None:
            outcome = "timeout"; exit_price = closes[min(i+max_hold, len(df)-1)]
        trades += 1
        if outcome == "win": wins += 1
        ret = ((exit_price - entry) / entry) * d
        pnl += ret
        pnl_pct_list.append(ret)
        i += max_hold  # no overlapping positions (hold-based)
    if trades == 0:
        return {"name": name, "trades": 0, "wr": 0, "pnl_pct": 0}
    return {"name": name, "trades": trades, "wr": round(wins/trades*100,1),
            "pnl_pct": round(pnl*100,2), "avg_ret": round(np.mean(pnl_pct_list)*100,3)}

def main():
    df = get_klines("PAXGUSDT", "1d", 400)
    df = df.tail(200).reset_index(drop=True)  # last ~200 days
    df["sma10"] = sma(df["close"], 10)
    df["sma20"] = sma(df["close"], 20)
    df["sma50"] = sma(df["close"], 50)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi14"] = rsi(df["close"], 14)
    df["atr14"] = atr(df, 14)
    df["mom5"] = df["close"].pct_change(5)
    df["mom10"] = df["close"].pct_change(10)
    df["macd"] = ema(df["close"], 12) - ema(df["close"], 26)
    df["macd_sig"] = ema(df["macd"], 9)

    # Current signal: price > SMA10 AND mom5 > 0 (validated Aug 6)
    df["sig_current"] = np.where((df["close"] > df["sma10"]) & (df["mom5"] > 0), 1.0, np.nan)
    df["dir_current"] = np.where((df["close"] > df["sma10"]) & (df["mom5"] > 0), 1, None)

    # Variant A: current + RSI(14) > 55 (strong momentum filter)
    df["dir_rsi"] = np.where((df["close"] > df["sma10"]) & (df["mom5"] > 0) & (df["rsi14"] > 55), 1, None)
    df["sig_rsi"] = df["dir_rsi"].astype(float)

    # Variant B: EMA20 > EMA50 (trend) + mom5 > 0
    df["dir_ema"] = np.where((df["ema20"] > df["ema50"]) & (df["mom5"] > 0), 1, None)
    df["sig_ema"] = df["dir_ema"].astype(float)

    # Variant C: MACD > signal + price > SMA20
    df["dir_macd"] = np.where((df["macd"] > df["macd_sig"]) & (df["close"] > df["sma20"]), 1, None)
    df["sig_macd"] = df["dir_macd"].astype(float)

    # Variant D: all three agree (RSI + EMA + MACD)
    df["dir_all"] = np.where((df["dir_rsi"] == 1) & (df["dir_ema"] == 1) & (df["dir_macd"] == 1), 1, None)
    df["sig_all"] = df["dir_all"].astype(float)

    print(f"PAXG last close: {df['close'].iloc[-1]:.2f} | ATR14: {df['atr14'].iloc[-1]:.2f} ({df['atr14'].iloc[-1]/df['close'].iloc[-1]*100:.2f}%)")
    print(f"Daily ATR% matters: 0.2% SL = {0.002*df['close'].iloc[-1]:.1f}$ on gold — vs avg daily range ~{df['high'].iloc[-1]-df['low'].iloc[-1]:.0f}$\n")

    print("=== TP +0.3% / SL -0.2% (current) ===")
    for col, nm in [("sig_current","CURRENT (SMA10+mom5)"), ("sig_rsi","+RSI>55"), ("sig_ema","EMA20>50+mom5"), ("sig_macd","MACD+SMA20"), ("sig_all","ALL AGREE")]:
        r = backtest(df, df[col], df[col.replace("sig","dir")], 0.003, 0.002, 5, nm)
        print(f"  {nm:24s} trades={r['trades']:3d}  WR={r['wr']:5.1f}%  PnL={r['pnl_pct']:+6.2f}%")

    print("\n=== TP +0.5% / SL -0.5% (wider, still cycle-ish) ===")
    for col, nm in [("sig_current","CURRENT"), ("sig_rsi","+RSI>55"), ("sig_ema","EMA20>50"), ("sig_macd","MACD"), ("sig_all","ALL AGREE")]:
        r = backtest(df, df[col], df[col.replace("sig","dir")], 0.005, 0.005, 5, nm)
        print(f"  {nm:24s} trades={r['trades']:3d}  WR={r['wr']:5.1f}%  PnL={r['pnl_pct']:+6.2f}%")

    print("\n=== ATR-based stop (SL=1.0 ATR, TP=1.5 ATR, hold 5) ===")
    for col, nm in [("sig_current","CURRENT"), ("sig_rsi","+RSI>55"), ("sig_ema","EMA20>50"), ("sig_macd","MACD"), ("sig_all","ALL AGREE")]:
        r = backtest(df, df[col], df[col.replace("sig","dir")], 0.003, 0.002, 5, nm, atr_stop=True)
        print(f"  {nm:24s} trades={r['trades']:3d}  WR={r['wr']:5.1f}%  PnL={r['pnl_pct']:+6.2f}%  avgRet={r.get('avg_ret','')}")

    print("\n=== Recent 10 bars (what the bot saw) ===")
    for i in range(len(df)-10, len(df)):
        d = df.iloc[i]
        print(f"  {d['date'].strftime('%m-%d')} close={d['close']:.0f} sma10={d['sma10']:.0f} rsi={d['rsi14']:.0f} atr={d['atr14']:.1f} mom5={d['mom5']*100:+.2f}% macd={'pos' if d['macd']>d['macd_sig'] else 'neg'}")

if __name__ == "__main__":
    main()
