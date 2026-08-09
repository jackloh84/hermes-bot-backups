#!/usr/bin/env python3
"""trading_master_doc.py — Jack's FULL trading command-center report.

One document with EVERYTHING:
  1. TOTAL WALLET (hot + main, USDC + ETH, all lanes)
  2. GAINS lane: open position (entry/TP/SL/strength/PnL), today, all-time
  3. LIMITLESS lane: day, bets, claims, streak, PnL
  4. TARGET RULES: what qualifies as a STRONG signal + exact stake amounts
  5. PREDICTION

Usage:
  python3 trading_master_doc.py              # print report
  python3 trading_master_doc.py --feishu     # print + send to Jack's Lark
"""
import json, os, sys, datetime, urllib.request

# ---------- addresses ----------
HOT = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
MAIN = "0xf52af41e893c1f230a3db3bd07cd8417b2277e5c"  # Jack's main wallet
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
RPC = "https://mainnet.base.org"

GAINS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/gains_intraday_state.json"
LIMITLESS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/limitless_state.json"
PROFIT_BANK_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/limitless_profit_bank.json"

USDC_ABI = '[{"constant":true,"inputs":[{"name":"a","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def wallet():
    """Return dict: hot_usdc, hot_eth, main_usdc, main_eth."""
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RPC))
        abi = json.loads(USDC_ABI)
        usdc = w3.eth.contract(Web3.to_checksum_address(USDC), abi=abi)
        main_full = MAIN
        pb = load(PROFIT_BANK_STATE)
        if pb.get("main_wallet"):
            main_full = pb["main_wallet"]
        out = {}
        out["hot_usdc"] = usdc.functions.balanceOf(Web3.to_checksum_address(HOT)).call() / 1e6
        out["hot_eth"] = w3.eth.get_balance(Web3.to_checksum_address(HOT)) / 1e18
        if main_full and main_full.startswith("0x"):
            out["main_usdc"] = usdc.functions.balanceOf(Web3.to_checksum_address(main_full)).call() / 1e6
            out["main_eth"] = w3.eth.get_balance(Web3.to_checksum_address(main_full)) / 1e18
        else:
            out["main_usdc"] = out["main_eth"] = None
        return out
    except Exception as e:
        return {"error": str(e)[:100]}


def gains_position():
    """Live open trade from Gains backend."""
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://backend-base.gains.trade/open-trades",
            headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
        for t in d:
            tr = t.get("trade", {})
            if str(tr.get("user", "")).lower() == HOT.lower():
                return tr
    except Exception:
        pass
    return None


def main():
    to_feishu = "--feishu" in sys.argv
    w = wallet()
    g = load(GAINS_STATE)
    l = load(LIMITLESS_STATE)
    tr = gains_position()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M SGT")

    out = []
    out.append(f"📊 JACK'S TRADING COMMAND CENTER — {now}")
    out.append("")

    # ---------- 1) TOTAL WALLET ----------
    out.append("💰 TOTAL WALLET")
    if "error" in w:
        out.append(f"  (wallet read error: {w['error']})")
    else:
        hot_usdc = w["hot_usdc"]
        hot_eth = w["hot_eth"]
        main_usdc = w["main_usdc"]
        main_eth = w["main_eth"]
        eth_usd = 0.0
        try:
            px = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
                headers={"User-Agent": "curl/7.81.0"}), timeout=10).read())
            eth_usd = float(px["price"])
        except Exception:
            pass
        total = hot_usdc + (hot_eth * eth_usd)
        if main_usdc is not None:
            total += main_usdc + (main_eth * eth_usd)
        out.append(f"  HOT  wallet: ${hot_usdc:.2f} USDC + {hot_eth:.4f} ETH (≈${hot_eth*eth_usd:.2f})")
        if main_usdc is not None:
            out.append(f"  MAIN wallet: ${main_usdc:.2f} USDC + {main_eth:.4f} ETH")
        out.append(f"  **TOTAL ≈ ${total:.2f}** (ETH @ ${eth_usd:.0f})")

    out.append("")

    # ---------- 2) GAINS ----------
    out.append("🥇 GAINS (XAU/BTC/ETH on-chain perps)")
    gw, gl = g.get("wins", 0), g.get("losses", 0)
    gt = gw + gl
    gpct = (gw / gt * 100) if gt else 0
    out.append(f"  Win rate {gpct:.0f}% ({gw}W/{gl}L) | Realized ${g.get('realized', 0):+.2f} | Bankroll ${g.get('bankroll', 0):.2f}")
    if tr:
        op = float(tr.get("openPrice", 0) or 0) / 1e10
        long = tr.get("long", True)
        pidx = int(tr.get("pairIndex", 90))
        coll = float(tr.get("collateralAmount", 0) or 0) / 1e6
        lev = float(tr.get("leverage", 0) or 0) / 1e3
        pair = {90: "XAUUSD", 0: "BTCUSD", 1: "ETHUSD"}.get(pidx, f"PAIR{pidx}")
        # live price
        try:
            d2 = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://backend-pricing.eu.gains.trade/charts",
                headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
            px = float(d2["closes"][pidx])
        except Exception:
            px = op
        pnl = ((px - op) / op) * lev * coll if long else ((op - px) / op) * lev * coll
        st_open = g.get("open") or {}
        tp = st_open.get("tp") or (op * (1 + 1.5 * 0.0025))
        sl = st_open.get("sl") or (op * (1 - 1.0 * 0.0025))
        d = "LONG" if long else "SHORT"
        out.append(f"  OPEN: {d} {pair} @{op:.2f} now {px:.2f} (PnL {pnl:+.2f})")
        out.append(f"        TP {tp:.2f} | SL {sl:.2f} | Collateral ${coll:.2f} @{lev:.0f}x")
    else:
        out.append("  No open position — waiting for strong signal")

    out.append("")

    # ---------- 3) LIMITLESS ----------
    out.append("🪙 LIMITLESS (up/down prediction bets)")
    trades = l.get("trades", [])
    claimed = l.get("claimed", [])
    out.append(f"  Bets logged {len(trades)} | Claims {len(claimed)} | Day {l.get('day', '?')}")
    out.append(f"  Day PnL ${l.get('day_pnl', 0):+.2f} | Loss streak {l.get('loss_streak', 0)} | Paused until {l.get('pause_until', 0)}")
    if trades:
        last = trades[-1]
        out.append(f"  Last bet: {last.get('side', '?').upper()} {last.get('slug', '?')} ${last.get('amount', 0)} "
                   f"(strength {last.get('strength', 0):.3f}%)")

    out.append("")

    # ---------- 4) TARGET RULES ----------
    out.append("🎯 STRONG-SIGNAL TARGET RULES (what the bot waits for)")
    out.append("  GAINS   : strength ≥ 1.0 (EMA20 + 3-bar momentum), 2-way")
    out.append("           stake $1.43 @200x (BTC/ETH) / $1.14 @250x (XAU)")
    out.append("           TP = +1.5×ATR | SL = −1.0×ATR | profit-lock by strength")
    out.append("  LIMITLESS: 1-min candle ≥ 0.10% + volume ≥ 2× + regime active")
    out.append("           token ≤ $0.45 (win pays ≥ 1.22×) | stake $1 base")
    out.append("  DAILY    : −3% stop | max 8-10 trades | win-rate stop after profit")

    out.append("")

    # ---------- 5) PREDICTION ----------
    out.append("🔮 PREDICTION")
    if tr:
        d = "LONG" if tr.get("long", True) else "SHORT"
        pair = {90: "XAUUSD", 0: "BTCUSD", 1: "ETHUSD"}.get(int(tr.get("pairIndex", 90)), "?")
        out.append(f"  Gains {d} {pair} running to TP/SL — managed every minute, ATR-based.")
    else:
        out.append("  Waiting for STRONG signal before next trade — no forced weak bets.")
    out.append("  Limitless: bets only on strong candles; banked via auto-claim.")
    out.append("  Plan: grind win rate > 50% with small stakes, then scale on your top-up.")

    report = "\n".join(out)
    print(report)

    if to_feishu:
        try:
            import subprocess
            subprocess.run(["python3",
                            "/home/ubuntu/.hermes/profiles/bot4/scripts/notify_feishu.py",
                            report], timeout=90)
            print("\n[sent to Feishu]")
        except Exception as e:
            print(f"\n[feishu send failed: {e}]")


if __name__ == "__main__":
    main()
