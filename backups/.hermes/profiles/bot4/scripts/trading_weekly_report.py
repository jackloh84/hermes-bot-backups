#!/usr/bin/env python3
"""trading_weekly_report.py — weekly win-rate/loss-rate + prediction report (Feishu).

Reads Gains + Limitless state files and prints a weekly summary:
total trades, win rate vs breakeven, expectancy, realized PnL, bankroll
trend, open positions, and a next-week prediction.

Usage: python3 trading_weekly_report.py
"""
import json, datetime

GAINS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/gains_intraday_state.json"
LIMITLESS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/limitless_state.json"


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def main():
    g = load(GAINS_STATE)
    l = load(LIMITLESS_STATE)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    gw, gl = g.get("wins", 0), g.get("losses", 0)
    gt = gw + gl
    gpct = (gw / gt * 100) if gt else 0
    lw = len(l.get("claimed", []))
    lbets = len(l.get("trades", []))

    out = []
    out.append(f"📈 Trading Weekly Report — {now}")
    out.append("")
    out.append("🥇 GAINS (XAU/BTC/ETH):")
    out.append(f"  Total trades {gt} | Win rate {gpct:.0f}% ({gw}W/{gl}L)")
    out.append(f"  Realized ${g.get('realized', 0):+.2f} | Bankroll ${g.get('bankroll', 0):.2f}")
    if g.get("open"):
        d = g["open"].get("direction", "?").upper()
        out.append(f"  OPEN: {d} {g['open'].get('pair', '?')} @{g['open'].get('entry', 0):.2f}")
    else:
        out.append("  No open position")
    out.append("")
    out.append("🪙 LIMITLESS (up/down):")
    out.append(f"  Bets logged {lbets} | Claims {lw}")
    out.append(f"  Day PnL ${l.get('day_pnl', 0):+.2f} | Streak {l.get('loss_streak', 0)}")
    out.append("")
    out.append("📊 COMBINED:")
    out.append(f"  Wins {gw + lw} / Losses {gl + max(0, lbets - lw)} (approx)")

    # Prediction
    breakeven_gains = 40.0  # TP 1.5×ATR vs SL 1.0×ATR
    verdict = "edge proving" if (gt >= 10 and gpct > breakeven_gains) else "still proving — need more strong-signal trades"
    out.append("")
    out.append(f"🔮 Prediction: {verdict}. Strategy stays: strong-signal-only, ATR stops, "
               "honest loss tracking. Next week = more trades only if signals qualify.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
