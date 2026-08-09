#!/usr/bin/env python3
"""trading_daily_report.py — daily win-rate/loss-rate report for Jack (Feishu).

Reads both state files (Gains intraday + Limitless) and prints a compact
report that the cron delivers to Feishu. Includes win rate, loss rate,
realized PnL, bankroll, open positions, and a prediction line.

Usage: python3 trading_daily_report.py
"""
import json, os, datetime, urllib.request

GAINS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/gains_intraday_state.json"
LIMITLESS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/limitless_state.json"


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def gains_report(st):
    if not st:
        return "  no state"
    wr = st.get("wins", 0), st.get("losses", 0)
    total = wr[0] + wr[1]
    pct = (wr[0] / total * 100) if total else 0
    open_pos = st.get("open")
    lines = [
        f"  Trades {total} | Win rate {pct:.0f}% ({wr[0]}W/{wr[1]}L)",
        f"  Realized ${st.get('realized', 0):+.2f} | Bankroll ${st.get('bankroll', 0):.2f}",
    ]
    if open_pos:
        d = open_pos.get("direction", "?").upper()
        lines.append(f"  OPEN: {d} {open_pos.get('pair', '?')} @{open_pos.get('entry', 0):.2f} "
                     f"TP {open_pos.get('tp', 0):.2f} / SL {open_pos.get('sl', 0):.2f}")
    else:
        lines.append("  No open position")
    return "\n".join(lines)


def limitless_report(st):
    if not st:
        return "  no state"
    trades = st.get("trades", [])
    claimed = st.get("claimed", [])
    # win/loss from claims + day_pnl signal; best-effort
    day = st.get("day", "?")
    lines = [
        f"  Bets logged: {len(trades)} | Claims: {len(claimed)}",
        f"  Day {day} PnL ${st.get('day_pnl', 0):+.2f} | Streak {st.get('loss_streak', 0)}",
    ]
    return "\n".join(lines)


def main():
    g = load(GAINS_STATE)
    l = load(LIMITLESS_STATE)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = []
    out.append(f"📊 Trading Daily Report — {now}")
    out.append("")
    out.append("🥇 GAINS (XAU/BTC/ETH):")
    out.append(gains_report(g))
    out.append("")
    out.append("🪙 LIMITLESS (up/down):")
    out.append(limitless_report(l))
    out.append("")
    # Prediction line (simple, honest)
    if g.get("open"):
        d = g["open"].get("direction", "long").upper()
        out.append(f"🔮 Prediction: GAINS {d} {g['open'].get('pair', '?')} running "
                   f"to TP/SL — ATR-based, managed every minute.")
    else:
        out.append("🔮 Prediction: waiting for STRONG signal (strength ≥1.0 Gains / ≥0.10% Limitless) before next trade.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
