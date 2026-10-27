"""Where the gold price and volatility come from.

Kalshi's daily gold markets settle on Pyth's gold price, so we read the live
price from Pyth too. Volatility comes from recent daily gold futures closes on
Yahoo Finance, with a fallback number if that download fails.
"""

import math

import requests

HERMES = "https://hermes.pyth.network"


def pyth_gold_feed_id() -> str:
    r = requests.get(f"{HERMES}/v2/price_feeds", params={"query": "XAU/USD", "asset_type": "metal"}, timeout=15)
    r.raise_for_status()
    for feed in r.json():
        if feed.get("attributes", {}).get("symbol", "").upper() == "METAL.XAU/USD":
            return feed["id"]
    raise RuntimeError("Could not find Pyth's XAU/USD feed")


def pyth_gold_price(feed_id: str) -> float:
    r = requests.get(f"{HERMES}/v2/updates/price/latest", params={"ids[]": feed_id}, timeout=15)
    r.raise_for_status()
    p = r.json()["parsed"][0]["price"]
    return int(p["price"]) * 10 ** int(p["expo"])


def daily_vol_from_closes(closes: list[float]) -> float:
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    if len(rets) < 2:
        raise ValueError("Need at least 3 closes to estimate volatility")
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((x - mean) ** 2 for x in rets) / (len(rets) - 1))


def realized_daily_vol(days: int = 30) -> float:
    """Standard deviation of gold's daily moves over roughly the last `days` trading days."""
    import yfinance as yf

    hist = yf.Ticker("GC=F").history(period="3mo", interval="1d")
    closes = [float(c) for c in hist["Close"].dropna().tolist()][-(days + 1):]
    return daily_vol_from_closes(closes)
