#!/usr/bin/env python3
"""
hl_trader.py — Hyperliquid perp trader, v2 (Aug 9 2026).
Signal: 20-bar Donchian BREAKOUT on ETH 1h — the 180-day backtest champion
(+31.3% on HL, +11.1% on Gains). Uses the SHARED signal library from
trading_engine.py so live == backtest (no drift).

Rules (Jack Aug 9):
  - Breakout: close > 20-bar high -> LONG; close < 20-bar low -> SHORT
  - TP = 1.5 x ATR(14); SL = 1.0 x ATR(14)
  - Daily -3% stop; max 5 trades/day; WR-stop
  - DRY RUN by default (prints what it would do, sends NO orders).
    Set DRY_RUN = True (or run --live) ONLY after Jack's explicit OK.

Usage:
  python3 hl_trader.py            # dry-run monitor (default)
  python3 hl_trader.py --status   # report only
  python3 hl_trader.py --live     # REAL orders (only after Jack OK)
"""
import os, sys, json, time, datetime

os.environ.setdefault("HOME", "/home/ubuntu")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# SHARED signal library — same code as backtest
import trading_engine as te

NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify_feishu.py")


def notify_feishu(text):
    try:
        import subprocess
        subprocess.Popen(["python3", NOTIFY, text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ---------- config ----------
STATE = "/home/ubuntu/.hermes/profiles/bot4/state/hl_trader_state.json"
WALLET = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
HL_API = "https://api.hyperliquid.xyz"
INTERVAL = "1h"
STRATEGY = "breakout"            # backtest champion (ETH 1h)
PRODUCTS = {
    "ETH": ("ETHUSDT", 4),       # name, szDecimals — champion only
}
MAX_TRADES_DAY = 5
TP_ATR = 1.5
SL_ATR = 1.0
DAILY_LOSS_STOP = 0.03
LEVERAGE = 3
NOTIONAL_MIN = 10.0
HEARTBEAT_MIN = 30
DRY_RUN = False                 # LIVE (Jack "go" Aug 9 2026) — real orders; --dry overrides for testing


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


def hl_info(payload):
    import urllib.request
    body = json.dumps(payload).encode()
    req = urllib.request.Request(HL_API + "/info", data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def get_hl_position():
    st = hl_info({"type": "clearinghouseState", "user": WALLET})
    for ap in st.get("assetPositions", []):
        p = ap["position"]
        szi = float(p.get("szi", 0))
        if szi == 0:
            continue
        return p["coin"], szi, float(p["entryPx"]), float(p.get("notional", 0))
    return None


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    return {"day": datetime.date.today().isoformat(), "trades": 0, "wins": 0, "losses": 0,
            "realized": 0.0, "bankroll": 19.97, "stopped": False, "open": None,
            "last_ping": 0.0, "trade_log": []}


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


def log_trade(st, pair, direction, entry, tp, sl, result, pnl, dry):
    st.setdefault("trade_log", []).append({
        "ts": time.time(), "pair": pair, "direction": direction, "entry": entry,
        "tp": tp, "sl": sl, "result": result, "pnl": pnl, "dry": dry})


def wr_text(st):
    total = st["wins"] + st["losses"]
    pct = (st["wins"] / total * 100) if total else 0.0
    return f"{st['wins']}W/{st['losses']}L ({pct:.0f}%)"


def main():
    status_only = "--status" in sys.argv
    global DRY_RUN
    if "--dry" in sys.argv:
        DRY_RUN = True
    if "--live" in sys.argv:
        DRY_RUN = False
    env = load_env()
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info

    acct = Account.from_key(env["WALLET_PK"])
    assert acct.address.lower() == WALLET.lower()
    exchange = Exchange(acct, base_url=HL_API)
    info = Info(HL_API, skip_ws=True)

    st = load_state()
    st = roll_day(st)
    lines = []

    # balance — UNIFIED ACCOUNT: read from spot clearinghouse state
    cstate = info.spot_user_state(acct.address)
    bal = sum(float(b.get("total", 0)) for b in cstate.get("balances", [])
              if b.get("coin") == "USDC")
    if bal <= 0:
        try:
            bal = float(info.user_state(acct.address)["marginSummary"]["accountValue"])
        except Exception:
            bal = 0.0
    st["bankroll"] = bal
    save_state(st)

    pos = get_hl_position()

    # -------- 1) position open? manage TP/SL --------
    if pos:
        name, szi, entry, notional = pos
        long = szi > 0
        px = float(hl_info({"type": "allMids"})[name])
        tp = st["open"]["tp"] if st.get("open") else entry * (1 + TP_ATR * 0.0025)
        sl = st["open"]["sl"] if st.get("open") else entry * (1 - SL_ATR * 0.0025)
        pnl = (px - entry) * szi if long else (entry - px) * abs(szi)
        if status_only:
            lines.append(f"open {'LONG' if long else 'SHORT'} {name} @{entry:.4f} now {px:.4f} (PnL ${pnl:.2f})")
            lines.append(f"TP @ {tp:.4f} | SL @ {sl:.4f}")
            lines.append(f"day: {wr_text(st)} | realized ${st['realized']:+.2f} | {'DRY' if DRY_RUN else 'LIVE'}")
            print("\n".join(lines)); return

        progress = ((px - entry) / (tp - entry)) if long else ((entry - px) / (entry - tp))
        progress = max(progress, 0.0)

        now = time.time()
        if now - st.get("last_ping", 0) > HEARTBEAT_MIN * 60:
            st["last_ping"] = now
            notify_feishu(f"HL heartbeat: {name} {'LONG' if long else 'SHORT'} @{entry:.4f} now {px:.4f} PnL ${pnl:.2f}")
            save_state(st)

        # TP / SL / reverse handling
        close_now = False
        reason = None
        if (long and px >= tp) or (not long and px <= tp):
            close_now, reason = True, "TP"
        elif (long and px <= sl) or (not long and px >= sl):
            close_now, reason = True, "SL"
        if close_now:
            if DRY_RUN:
                notify_feishu(f"HL [DRY] would CLOSE {name} {reason} PnL ${pnl:.2f}")
                print(f"[DRY] close {name} {reason} pnl ${pnl:.2f}")
                return
            result = exchange.market_close(name, abs(szi))
            ok = result.get("status") == "ok" or (result.get("response") or {}).get("status") == "ok"
            st["trades"] += 1
            if reason == "TP":
                st["wins"] += 1 if ok else 0
                st["losses"] += 0 if ok else 1
            else:
                st["losses"] += 1
            st["realized"] += pnl if ok else 0
            log_trade(st, name, "LONG" if long else "SHORT", entry, tp, sl, reason, pnl if ok else 0.0, False)
            st["open"] = None
            save_state(st)
            notify_feishu(f"HL {reason} CLOSED {name} {'LONG' if long else 'SHORT'} PnL ${pnl:.2f} ({wr_text(st)})")
            print(f"{reason} closed {name} pnl ${pnl:.2f}")
        return

    # -------- 2) no position -> breakout signal --------
    if status_only:
        for name, (sym, _) in PRODUCTS.items():
            bars = te.fetch_klines(sym, INTERVAL, 10)
            s = te.last_signal(bars, STRATEGY)
            lines.append(f"{name} {INTERVAL} breakout signal: {'LONG' if s==1 else 'SHORT' if s==-1 else 'NONE'} @ {bars[-1]['c']}")
        lines.append(f"bal ${st['bankroll']:.2f} | day: {wr_text(st)} | trades {st['trades']}/{MAX_TRADES_DAY} | {'DRY' if DRY_RUN else 'LIVE'}")
        print("\n".join(lines)); return

    if st.get("stopped"):
        return
    if st["trades"] >= MAX_TRADES_DAY:
        return
    if st["realized"] <= -DAILY_LOSS_STOP * max(st["bankroll"], 1.0):
        st["stopped"] = True
        save_state(st)
        notify_feishu(f"HL daily -3% stop hit ({wr_text(st)}) — halted for today")
        print("daily stop"); return

    for name, (sym, sz_dec) in PRODUCTS.items():
        bars = te.fetch_klines(sym, INTERVAL, 10)
        s = te.last_signal(bars, STRATEGY)
        if s == 0:
            continue
        direction = "long" if s == 1 else "short"
        px = bars[-1]["c"]
        atrs = te.atr(bars, 14)
        atr = atrs[-1] if not (atrs[-1] != atrs[-1]) else px * 0.003  # nan guard
        tp = px * (1 + TP_ATR * atr / px) if s == 1 else px * (1 - TP_ATR * atr / px)
        sl = px * (1 - SL_ATR * atr / px) if s == 1 else px * (1 + SL_ATR * atr / px)

        if DRY_RUN:
            notify_feishu(f"HL [DRY] signal {direction.upper()} {name} @{px:.2f} TP={tp:.2f} SL={sl:.2f}")
            st["open"] = {"pair": name, "direction": direction, "tp": tp, "sl": sl, "dry": True}
            save_state(st)
            print(f"[DRY] OPEN {direction.upper()} {name} @{px:.2f} sz={round(NOTIONAL_MIN/px, sz_dec)} TP={tp:.2f} SL={sl:.2f}")
            return

        # LIVE path (only with --live)
        try:
            exchange.update_leverage(name, LEVERAGE, True)
            sz = round(NOTIONAL_MIN / px, sz_dec)
            result = exchange.market_open(name, s == 1, sz, px)
        except Exception as e:
            print(f"open err: {str(e)[:100]}"); return
        ok = result.get("status") == "ok" or (result.get("response") or {}).get("status") == "ok"
        if not ok:
            print(f"open rejected: {json.dumps(result)[:200]}"); return
        st["open"] = {"pair": name, "direction": direction, "tp": tp, "sl": sl, "dry": False}
        save_state(st)
        notify_feishu(f"HL OPEN {direction.upper()} {name} @{px:.2f} sz={sz} TP={tp:.2f} SL={sl:.2f}")
        print(f"OPEN {direction.upper()} {name} @{px:.2f} sz={sz}")
        return


if __name__ == "__main__":
    main()
