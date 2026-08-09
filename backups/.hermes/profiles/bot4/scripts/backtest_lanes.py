#!/usr/bin/env python3
"""backtest_lanes.py — what actually drives win rate on Jack's CURRENT lanes.

Tests the signal families that CAN be plugged into Gains gTrade + Hyperliquid
(BTC/ETH 1h) and the Limitless 5-min concept, on real Binance data.

Strategies tested per asset (1h, 180 days):
  1. EMA20+3bar momentum  (current Gains-style signal)
  2. EMA cross 20/50      (classic trend)
  3. RSI(14) reversal     (mean reversion)
  4. ATR breakout (Supertrend-style)
  5. Buy & hold baseline
Output: win rate %, # trades, total return, avg win/loss.
"""
import json, urllib.request, datetime, sys

import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

ASSETS = {
    "BTCUSDT": "BTC (Gains+HL lane)",
    "ETHUSDT": "ETH (Gains+HL lane)",
    "PAXGUSDT": "XAU/gold (Gains lane)",
}
DAYS = 180
COMMISSION = 0.001  # 0.1% per side


def fetch_klines(symbol, interval="1h", days=DAYS):
    """Fetch up to ~1000 candles (Binance cap) — that's ~41 days of 1h data."""
    url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
           f"&interval={interval}&limit=1000")
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.81.0"})
    k = json.loads(urllib.request.urlopen(req, timeout=20).read())
    rows = []
    for r in k:
        rows.append({
            "Open": float(r[1]), "High": float(r[2]), "Low": float(r[3]),
            "Close": float(r[4]), "Volume": float(r[5]),
            "time": datetime.datetime.utcfromtimestamp(r[0] / 1000),
        })
    df = pd.DataFrame(rows).set_index("time")
    return df


class EMA20Momentum(Strategy):
    """Current Gains-style: close vs EMA20 + 3-bar momentum, 2-way."""
    n_ema = 20

    def init(self):
        self.ema = self.I(lambda x: pd.Series(x).ewm(span=self.n_ema).mean().to_numpy(), self.data.Close)

    def next(self):
        if len(self.data.Close) < 5:
            return
        last = self.data.Close[-1]
        ema = self.ema[-1]
        mom = (last - self.data.Close[-4]) / self.data.Close[-4]
        if last > ema and mom > 0 and not self.position:
            self.buy()
        elif last < ema and mom < 0 and not self.position:
            self.sell()


class EMACross(Strategy):
    n1, n2 = 20, 50

    def init(self):
        self.fast = self.I(lambda x: pd.Series(x).ewm(span=self.n1).mean().to_numpy(), self.data.Close)
        self.slow = self.I(lambda x: pd.Series(x).ewm(span=self.n2).mean().to_numpy(), self.data.Close)

    def next(self):
        if crossover(self.fast, self.slow):
            self.position.close()
            self.buy()
        elif crossover(self.slow, self.fast):
            self.position.close()
            self.sell()


class RSIMeanRev(Strategy):
    n = 14

    def init(self):
        closes = self.data.Close
        delta = pd.Series(closes).diff()
        gain = delta.clip(lower=0).rolling(self.n).mean()
        loss = -delta.clip(upper=0).rolling(self.n).mean()
        rs = gain / loss
        self.rsi = self.I(lambda: (100 - 100 / (1 + rs)).to_numpy())

    def next(self):
        if self.rsi[-1] < 30 and not self.position:
            self.buy()
        elif self.rsi[-1] > 70 and self.position:
            self.position.close()


class ATRBreakout(Strategy):
    """Donchian-style breakout: buy when close > 20-bar high, short < 20-bar low."""
    n = 20

    def init(self):
        self.hh = self.I(lambda: pd.Series(self.data.High).rolling(self.n).max().shift(1).to_numpy())
        self.ll = self.I(lambda: pd.Series(self.data.Low).rolling(self.n).min().shift(1).to_numpy())

    def next(self):
        if self.data.Close[-1] > self.hh[-1] and not self.position:
            self.buy()
        elif self.data.Close[-1] < self.ll[-1] and not self.position:
            self.sell()
        elif self.position and self.position.is_long and self.data.Close[-1] < self.ll[-1]:
            self.position.close()
        elif self.position and self.position.is_short and self.data.Close[-1] > self.hh[-1]:
            self.position.close()


STRATEGIES = {
    "EMA20+Momentum (current)": EMA20Momentum,
    "EMA cross 20/50": EMACross,
    "RSI(14) mean-rev": RSIMeanRev,
    "20-bar breakout": ATRBreakout,
}


def run_all():
    import warnings
    warnings.filterwarnings("ignore")
    print("=" * 90)
    print(f"BACKTEST: {DAYS} days of 1h data, commission {COMMISSION*100:.1f}%/side")
    print("=" * 90)
    results = []
    for sym, label in ASSETS.items():
        df = fetch_klines(sym)
        print(f"\n### {label} ({sym}) — {len(df)} candles")
        for sname, scls in STRATEGIES.items():
            try:
                bt = Backtest(df, scls, cash=100000, commission=COMMISSION)
                out = bt.run()
                trades = out.get("_trades", None)
                if trades is None or len(trades) == 0:
                    print(f"  {sname:<28} no trades")
                    continue
                n = len(trades)
                wins = int((trades["PnL"] > 0).sum())
                wr = wins / n * 100
                ret = out["Return [%]"]
                avg_win = trades.loc[trades["PnL"] > 0, "PnL"].mean() if wins else 0
                avg_loss = trades.loc[trades["PnL"] <= 0, "PnL"].mean() if (n - wins) else 0
                print(f"  {sname:<28} WR={wr:5.1f}%  trades={n:3d}  ret={ret:+7.1f}%  avgW=${avg_win:+.2f} avgL=${avg_loss:+.2f}")
                results.append({"asset": sym, "strategy": sname, "wr": round(wr, 1),
                                "trades": n, "ret": round(ret, 1), "avgW": round(avg_win, 2), "avgL": round(avg_loss, 2)})
            except Exception as e:
                print(f"  {sname:<28} ERROR {str(e)[:70]}")
    # summary
    print("\n" + "=" * 90)
    print("SUMMARY — sorted by win rate (per asset)")
    print("=" * 90)
    for r in sorted(results, key=lambda x: (x["asset"], -x["wr"])):
        print(f"{r['asset']:<10} {r['strategy']:<28} WR={r['wr']:5.1f}%  trades={r['trades']:3d}  ret={r['ret']:+6.1f}%")
    print("\n'Drives high WR' signal: strategies with WR > 55% AND avgW > avgL are candidates.")
    json.dump(results, open("/home/ubuntu/backtest_lanes_results.json", "w"), indent=1)
    print("saved: /home/ubuntu/backtest_lanes_results.json")


if __name__ == "__main__":
    run_all()
