"""Alert-only scanner for Kalshi gold markets. It never places orders.

Run:  python -m goldbot.scan            (one scan)
      python -m goldbot.scan --watch 60 (scan every 60 seconds)
"""

import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path

from .kalshi import Kalshi, dollars
from .model import best_trade, now_utc, trading_days_between, yes_probability
from .prices import pyth_gold_feed_id, pyth_gold_price, realized_daily_vol

LOG_FIELDS = ["time_utc", "ticker", "strike_type", "strike", "close_time", "spot", "daily_vol",
              "days_left", "model_prob", "yes_ask", "no_ask", "side", "price", "edge"]


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def scan_once(client: Kalshi, series: str, spot: float, daily_vol: float,
              min_edge: float, fee_rate: float, log_path: Path | None) -> list:
    now = now_utc()
    rows = []
    for m in client.open_markets(series):
        expiry = parse_time(m.get("expected_expiration_time") or m["close_time"])
        days_left = trading_days_between(now, expiry)
        st, floor, cap = m.get("strike_type"), m.get("floor_strike"), m.get("cap_strike")
        p_yes = yes_probability(st, floor, cap, spot, daily_vol, days_left)
        if p_yes is None:
            continue
        sig = best_trade(m["ticker"], floor if floor is not None else cap, st, p_yes,
                         dollars(m.get("yes_ask_dollars")), dollars(m.get("no_ask_dollars")),
                         min_edge, fee_rate)
        rows.append((m, days_left, sig))

    rows.sort(key=lambda r: r[2].strike or 0)
    print(f"\n{now:%Y-%m-%d %H:%M:%S} UTC  gold ${spot:,.2f}  daily vol {daily_vol:.2%}  ({len(rows)} markets)")
    print(f"{'ticker':<32}{'strike':>10}{'model':>8}{'yes ask':>9}{'no ask':>8}  signal")
    for m, days_left, s in rows:
        fmt = lambda v: f"{v:.2f}" if v is not None else "  -"
        flag = f"BUY {s.side} @ {s.price:.2f}  edge {s.edge:+.3f}" if s.side else ""
        print(f"{s.ticker:<32}{s.strike:>10,.2f}{s.model_prob:>8.1%}{fmt(s.yes_ask):>9}{fmt(s.no_ask):>8}  {flag}")

    if log_path:
        new = not log_path.exists()
        with log_path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if new:
                w.writeheader()
            for m, days_left, s in rows:
                w.writerow({"time_utc": now.isoformat(), "ticker": s.ticker, "strike_type": s.strike_type,
                            "strike": s.strike, "close_time": m["close_time"], "spot": spot,
                            "daily_vol": daily_vol, "days_left": round(days_left, 4),
                            "model_prob": round(s.model_prob, 4), "yes_ask": s.yes_ask, "no_ask": s.no_ask,
                            "side": s.side or "", "price": s.price or "",
                            "edge": round(s.edge, 4) if s.edge is not None else ""})
    return rows


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser(description="Compare a simple gold model with Kalshi prices (alerts only).")
    ap.add_argument("--series", default=os.getenv("GOLDBOT_SERIES", "KXGOLDD"), help="Kalshi series ticker")
    ap.add_argument("--min-edge", type=float, default=0.05, help="flag trades worth at least this many dollars per contract after fees")
    ap.add_argument("--fee-rate", type=float, default=0.07, help="Kalshi taker fee multiplier")
    ap.add_argument("--vol", type=float, help="daily volatility to use instead of downloading it, e.g. 0.012 for 1.2%%")
    ap.add_argument("--watch", type=int, metavar="SECONDS", help="keep scanning on this interval")
    ap.add_argument("--log", default="signals.csv", help="CSV file to record every scan ('' to turn off)")
    ap.add_argument("--show-rules", action="store_true", help="print the series' settlement source and rules first")
    args = ap.parse_args()

    client = Kalshi()
    if args.show_rules:
        s = client.series(args.series)
        print(f"{s.get('title')}  ({args.series})")
        for src in s.get("settlement_sources") or []:
            print(f"  settles on: {src.get('name')}  {src.get('url', '')}")
        if s.get("contract_url"):
            print(f"  full rules: {s['contract_url']}")

    if args.vol:
        daily_vol = args.vol
    else:
        try:
            daily_vol = realized_daily_vol()
        except Exception as e:
            daily_vol = 0.012
            print(f"Could not download volatility ({e}); using {daily_vol:.1%}. Pass --vol to set it.")

    feed = pyth_gold_feed_id()
    log_path = Path(args.log) if args.log else None
    while True:
        scan_once(client, args.series, pyth_gold_price(feed), daily_vol, args.min_edge, args.fee_rate, log_path)
        if not args.watch:
            break
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
