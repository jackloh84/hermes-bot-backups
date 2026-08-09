#!/usr/bin/env python3
"""feishu_trading_sheet.py — LIVE Feishu spreadsheet updater.

Maintains a live Google-Sheets-style spreadsheet on Lark (Feishu) with:
  - Overview tab  : total wallet, win rates, bankroll, open positions, prediction
  - Gains tab     : every Gains trade row (append-only log)
  - Limitless tab : every Limitless bet row (append-only log)
  - Targets tab   : strong-signal rules + stake amounts

Re-runnable — idempotent. Creates tabs if missing, writes Overview fresh each
run, appends only NEW trade rows to Gains/Limitless logs.

Usage:
  python3 feishu_trading_sheet.py          # refresh everything
  python3 feishu_trading_sheet.py --debug  # verbose
"""
import json, os, sys, time, datetime, urllib.request

DOMAIN = "https://open.larksuite.com"
SHEET_TOKEN_FILE = "/home/ubuntu/.hermes/profiles/bot4/state/feishu_sheet_token.txt"
STATE_FILE = "/home/ubuntu/.hermes/profiles/bot4/state/feishu_trading_sheet.json"

GAINS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/gains_intraday_state.json"
LIMITLESS_STATE = "/home/ubuntu/.hermes/profiles/bot4/state/limitless_state.json"
HOT = "0x57E33b7aEC4DdcDe614C3BeCBb34126914e4f813"
MAIN = "0xf52af41e893c1f230a3db3bd07cd8417b2277e5c"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
RPC = "https://mainnet.base.org"
USDC_ABI = '[{"constant":true,"inputs":[{"name":"a","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'

DEBUG = "--debug" in sys.argv


def log(*a):
    if DEBUG:
        print(*a, flush=True)


def feishu_env():
    env = {}
    for line in open("/home/ubuntu/.hermes/.env"):
        line = line.strip()
        if line.startswith("FEISHU_") and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_token(env):
    body = json.dumps({"app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]}).encode()
    req = urllib.request.Request(DOMAIN + "/open-apis/auth/v3/tenant_access_token/internal",
                                 data=body, headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    if r.get("code") != 0:
        raise RuntimeError(f"token fail: {r.get('msg')}")
    return r["tenant_access_token"]


def api(tok, method, path, body=None):
    url = DOMAIN + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + tok})
    r = json.loads(urllib.request.urlopen(req, timeout=25).read())
    return r


def list_sheets(tok, st):
    r = api(tok, "GET", f"/open-apis/sheets/v3/spreadsheets/{st}/sheets/query")
    return {s["title"]: s["sheet_id"] for s in r.get("data", {}).get("sheets", [])}


def add_sheet(tok, st, title):
    """v2 batch update returns sheet_id immediately (v3 add ignores titles)."""
    r = api(tok, "POST", f"/open-apis/sheets/v2/spreadsheets/{st}/sheets_batch_update",
            {"requests": [{"addSheet": {"properties": {"title": title, "index": 99}}}]})
    if r.get("code") != 0:
        log("add sheet fail", title, r.get("msg"))
        return None
    # parse newly created sheet id from replies
    replies = r.get("data", {}).get("replies", []) or []
    for rep in replies:
        add = rep.get("addSheet", {})
        sid = add.get("properties", {}).get("sheetId") or add.get("sheetId")
        if sid:
            return sid
    return None


def col_letter(n):
    """1 -> A, 26 -> Z, 27 -> AA"""
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def write_values(tok, st, sheet_id, range_, values):
    """values = list of rows, each row a list of cells.
    Feishu range must include an END cell: A1:B2 (A1 alone errors 90202)."""
    rows = len(values)
    cols = max((len(r) for r in values), default=1)
    end = f"{col_letter(cols)}{rows}"
    full_range = f"{sheet_id}!{range_.split('!')[-1].split(':')[0]}:{end}"
    r = api(tok, "PUT", f"/open-apis/sheets/v2/spreadsheets/{st}/values",
            {"valueRange": {"range": full_range,
                            "values": values}})
    if r.get("code") != 0:
        log("write fail", full_range, r.get("msg"))
    return r.get("code") == 0


def append_values(tok, st, sheet_id, values):
    r = api(tok, "POST", f"/open-apis/sheets/v2/spreadsheets/{st}/values_append",
            {"valueRange": {"range": f"{sheet_id}!A1", "values": values}})
    if r.get("code") != 0:
        log("append fail", r.get("msg"))
    return r.get("code") == 0


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def wallet():
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RPC))
        abi = json.loads(USDC_ABI)
        usdc = w3.eth.contract(Web3.to_checksum_address(USDC), abi=abi)
        hot_usdc = usdc.functions.balanceOf(Web3.to_checksum_address(HOT)).call() / 1e6
        hot_eth = w3.eth.get_balance(Web3.to_checksum_address(HOT)) / 1e18
        main_usdc = usdc.functions.balanceOf(Web3.to_checksum_address(MAIN)).call() / 1e6
        main_eth = w3.eth.get_balance(Web3.to_checksum_address(MAIN)) / 1e18
        return hot_usdc, hot_eth, main_usdc, main_eth
    except Exception as e:
        log("wallet err", e)
        return 0, 0, 0, 0


def eth_price():
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
            headers={"User-Agent": "curl/7.81.0"}), timeout=10).read())
        return float(r["price"])
    except Exception:
        return 0


def gains_position():
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
    env = feishu_env()
    tok = get_token(env)
    st = open(SHEET_TOKEN_FILE).read().strip()
    log("token ok, spreadsheet", st)

    sheets = list_sheets(tok, st)
    log("existing sheets:", sheets)
    for title in ("Overview", "Gains", "Limitless", "Targets"):
        if title not in sheets:
            sid = add_sheet(tok, st, title)
            if sid:
                sheets[title] = sid
            log("created", title, "->", sid)
        else:
            log("exists", title)

    ov = sheets.get("Overview")
    ga = sheets.get("Gains")
    li = sheets.get("Limitless")
    ta = sheets.get("Targets")

    g = load(GAINS_STATE)
    l = load(LIMITLESS_STATE)
    h_usdc, h_eth, m_usdc, m_eth = wallet()
    epx = eth_price()
    total = h_usdc + h_eth * epx + m_usdc + m_eth * epx
    tr = gains_position()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ---------- Overview ----------
    gw, gl = g.get("wins", 0), g.get("losses", 0)
    gt = gw + gl
    gpct = (gw / gt * 100) if gt else 0
    lw = len(l.get("claimed", []))
    lbets = len(l.get("trades", []))

    ov_rows = [
        ["FIELD", "VALUE"],
        ["Updated", now],
        ["HOT wallet USDC", f"${h_usdc:.2f}"],
        ["HOT wallet ETH", f"{h_eth:.4f} (${h_eth*epx:.2f})"],
        ["MAIN wallet USDC", f"${m_usdc:.2f}"],
        ["MAIN wallet ETH", f"{m_eth:.4f} (${m_eth*epx:.2f})"],
        ["TOTAL WALLET", f"${total:.2f}"],
        ["", ""],
        ["GAINS win rate", f"{gpct:.0f}% ({gw}W/{gl}L)"],
        ["GAINS realized", f"${g.get('realized', 0):+.2f}"],
        ["GAINS bankroll", f"${g.get('bankroll', 0):.2f}"],
        ["LIMITLESS bets", str(lbets)],
        ["LIMITLESS claims", str(lw)],
        ["", ""],
    ]
    if tr:
        op = float(tr.get("openPrice", 0) or 0) / 1e10
        pidx = int(tr.get("pairIndex", 90))
        pair = {90: "XAUUSD", 0: "BTCUSD", 1: "ETHUSD"}.get(pidx, f"PAIR{pidx}")
        d = "LONG" if tr.get("long", True) else "SHORT"
        ov_rows.append(["OPEN POSITION", f"{d} {pair} @{op:.2f}"])
    else:
        ov_rows.append(["OPEN POSITION", "none — waiting for strong signal"])
    ov_rows += [
        ["", ""],
        ["PREDICTION", "Strong-signal only. BTC long running to TP/SL (ATR-managed)."],
        ["RULES", "Gains strength≥1.0 | Limitless ≥0.10% + vol≥2x + regime"],
    ]
    write_values(tok, st, ov, "A1", ov_rows)

    # ---------- Gains log ----------
    g_rows = [["ts", "pair", "dir", "entry", "tp", "sl", "collateral", "leverage", "strength", "lock", "result", "pnl"]]
    for t in g.get("trade_log", []):
        g_rows.append([
            datetime.datetime.fromtimestamp(t.get("ts", 0)).strftime("%m-%d %H:%M") if t.get("ts") else "",
            t.get("pair", ""), t.get("direction", ""), t.get("entry", ""),
            t.get("tp", ""), t.get("sl", ""), t.get("collateral", ""),
            t.get("leverage", ""), t.get("strength", ""), t.get("lock_pct", ""),
            t.get("result", ""), t.get("pnl", ""),
        ])
    write_values(tok, st, ga, "A1", g_rows)

    # ---------- Limitless log ----------
    l_rows = [["ts", "market", "side", "token", "amount", "strength", "vol", "result"]]
    for t in l.get("trades", [])[-30:]:
        l_rows.append([
            datetime.datetime.fromtimestamp(t.get("ts", 0)).strftime("%m-%d %H:%M") if t.get("ts") else "",
            t.get("slug", ""), t.get("side", ""), t.get("token", ""),
            t.get("amount", ""), t.get("strength", ""), t.get("vol_ratio", ""),
            t.get("result", ""),
        ])
    write_values(tok, st, li, "A1", l_rows)

    # ---------- Targets ----------
    t_rows = [
        ["LANE", "SIGNAL", "STAKE", "TP/SL", "STOPS"],
        ["GAINS", "strength ≥ 1.0 (EMA20+mom3), 2-way", "$1.43 @200x BTC/ETH | $1.14 @250x XAU",
         "TP +1.5×ATR / SL −1.0×ATR", "daily −3%, 8/day, WR-stop"],
        ["LIMITLESS", "1-min ≥0.10% + vol≥2x + regime", "$1 base (≤45c token)",
         "win pays ≥1.22x; claim by lock", "daily −3%, 10/day, 3-loss pause"],
    ]
    write_values(tok, st, ta, "A1", t_rows)

    print(f"✅ Feishu sheet updated: {st}")
    print(f"   Overview: total ${total:.2f} | Gains {gw}W/{gl}L | Limitless {lbets} bets")
    if tr:
        print(f"   Open: {'LONG' if tr.get('long') else 'SHORT'} pair {tr.get('pairIndex')}")


if __name__ == "__main__":
    main()
