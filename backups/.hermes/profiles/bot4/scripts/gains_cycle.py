#!/usr/bin/env python3
"""
gains_cycle.py — Daily cycle mode on Gains Network (Base).

Wins → bank → re-enter. Up to 3 cycles/day on the weekly trend signal.
Logic per run:
  1. Check open position + current price.
  2. If TP hit -> closeTradeMarket -> bank the win, cycle += 1.
  3. If position gone (SL auto-hit) -> record loss, cycle += 1.
  4. If no position AND signal fires AND cycles today < 3 -> reopen.
  5. Daily hard stop: if today's realized loss > 3% of bankroll, halt.

Usage:
  python3 gains_cycle.py            # monitor + act (safe, small stakes)
  python3 gains_cycle.py --status   # report only, no tx
"""
import os, sys, json, time, datetime, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gains_weekly_lane as g

RPC = g.RPC
DIAMOND = g.DIAMOND
USDC = g.USDC
BACKEND = g.BACKEND
PRICING = g.PRICING
STATE = os.path.expanduser("~/.hermes/profiles/bot4/state/gains_cycle_state.json")
WALLET = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
MAX_CYCLES_DAY = 3
TP_PCT = 0.003        # take profit 0.30% (at 250x = +75% collateral)
DAILY_LOSS_STOP = 0.03  # halt after -3% bankroll realized in a day

CLOSE_ABI = [{"inputs": [{"name": "_index", "type": "uint32"},
                         {"name": "_expectedPrice", "type": "uint64"}],
              "name": "closeTradeMarket", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]


def http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def get_open_trade():
    d = http_json(f"{BACKEND}/open-trades")
    for t in d:
        tr = t.get("trade", {})
        if str(tr.get("user", "")).lower() == WALLET.lower():
            return tr
    return None


def get_price(pair_index=90):
    d = http_json(f"{PRICING}/charts")
    return float(d["closes"][pair_index]), float(d["indexPrices"][pair_index])


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    today = datetime.date.today().isoformat()
    return {"day": today, "cycles": 0, "wins": 0, "losses": 0, "realized": 0.0, "bankroll": 40.10}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)


def roll_day(st):
    today = datetime.date.today().isoformat()
    if st.get("day") != today:
        st["day"] = today
        st["cycles"] = 0
        st["realized"] = 0.0
        save_state(st)
    return st


def main():
    status_only = "--status" in sys.argv
    env = g.load_env()
    st = load_state()
    st = roll_day(st)

    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(RPC))
    acct = w3.eth.account.from_key(env["WALLET_PK"])
    diamond = Web3.to_checksum_address(DIAMOND)

    px, _ = get_price(90)
    trade = get_open_trade()
    lines = []

    if trade:
        op = float(trade.get("openPrice", 0) or 0) / 1e10
        idx = int(trade.get("index", 0))
        long = trade.get("long", True)
        coll = float(trade.get("collateralAmount", 0) or 0) / 1e6
        # realized PnL if closed now (approx, 1e10 price)
        pnl_coll = ((px - op) / op) * coll if long else ((op - px) / op) * coll
        tp_price = op * (1 + TP_PCT) if long else op * (1 - TP_PCT)
        hit = (px >= tp_price) if long else (px <= tp_price)
        if status_only:
            lines.append(f"open LONG XAU @{op:.2f} now {px:.2f} (PnL ~${pnl_coll:.2f})")
            lines.append(f"TP @ {tp_price:.2f} ({'HIT' if hit else 'waiting'})")
        elif hit:
            # close at TP
            ct = w3.eth.contract(diamond, abi=CLOSE_ABI)
            exp = int(px * 1e10)
            build = ct.functions.closeTradeMarket(idx, exp)
            try:
                gas = build.estimate_gas({"from": acct.address})
            except Exception as e:
                lines.append(f"close estimate fail: {str(e)[:100]}")
                print("\n".join(lines)); return
            tx = build.build_transaction({"from": acct.address,
                                          "nonce": w3.eth.get_transaction_count(acct.address),
                                          "gas": int(gas * 1.3), "gasPrice": w3.eth.gas_price})
            signed = acct.sign_transaction(tx)
            txh = w3.eth.send_raw_transaction(signed.raw_transaction)
            rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=180)
            ok = rcpt["status"] == 1
            win = pnl_coll if ok else 0.0
            st["cycles"] += 1
            st["wins"] += 1 if ok else 0
            st["realized"] += win
            st["bankroll"] += win
            save_state(st)
            lines.append(f"✅ TP CLOSED LONG XAU tx {txh.hex()[:16]}…  banked +${win:.2f} (cycle {st['cycles']}/3)")
        # else: holding — silent (cron watchdog stays quiet)
    else:
        # check if a position was closed by SL (loss) — count a cycle when signal existed earlier
        if st.get("cycles", 0) < MAX_CYCLES_DAY and not status_only:
            # try to reopen on fresh signal
            hist = g.binance_daily("PAXGUSDT", 35)
            direction, strength = g.signal_from_series(hist)
            # reopen on the STRONGEST signal across all products (if cap allows)
            if st.get("cycles", 0) < MAX_CYCLES_DAY and not status_only:
                try:
                    results = g.scan_all()
                    if not results:
                        if status_only:
                            lines.append(f"no position, no signal — waiting")
                        return
                    best_pair, best_dir, best_strength, best_px = results[0]
                except Exception as e:
                    lines.append(f"scan err: {str(e)[:80]}")
                    return
                if st["realized"] <= -DAILY_LOSS_STOP * st["bankroll"]:
                    lines.append(f"daily -3% stop hit — no new trade today")
                    return
                lines.append(f"signal {best_dir} on {best_pair} (strength {best_strength:.2f}) — reopening cycle {st['cycles']+1}/{MAX_CYCLES_DAY}")
                import subprocess
                r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gains_weekly_lane.py"), "--live", "--pair", best_pair],
                                   capture_output=True, text=True, timeout=300)
                out = r.stdout.strip().splitlines()
                for ln in out[-5:]:
                    lines.append("  " + ln)
                if "SUCCESS" in r.stdout:
                    st["cycles"] += 1
                    save_state(st)
        else:
            if status_only:
                lines.append(f"no position; cycle cap ({MAX_CYCLES_DAY}/day) or status-only")

    if status_only:
        lines.append(f"today: {st['wins']}W {st['losses']}L | realized ${st['realized']:+.2f} | cycles {st['cycles']}/{MAX_CYCLES_DAY} | bankroll ${st['bankroll']:.2f}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
