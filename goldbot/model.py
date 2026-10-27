"""Probability model and edge math.

The idea: gold's price at settlement is uncertain. If we know today's price and
how much gold usually moves in a day (volatility), we can estimate the chance it
finishes above any strike. We then compare that chance with Kalshi's price.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def trading_days_between(start: datetime, end: datetime) -> float:
    """Days of gold trading left, skipping Saturdays and Sundays.

    Gold barely moves on weekends, so counting them would overstate the risk.
    This is a simple approximation: weekday hours count, weekend hours don't.
    """
    if end <= start:
        return 0.0
    hours = 0.0
    t = start
    step = timedelta(minutes=15)
    while t < end:
        nxt = min(t + step, end)
        if t.weekday() < 5:
            hours += (nxt - t).total_seconds() / 3600.0
        t = nxt
    return hours / 24.0


def prob_above(spot: float, strike: float, daily_vol: float, days_left: float) -> float:
    """Chance the price ends above `strike`, assuming random lognormal moves.

    daily_vol is the standard deviation of daily log returns (e.g. 0.01 = 1%).
    """
    if days_left <= 0 or daily_vol <= 0:
        return 1.0 if spot > strike else 0.0
    sd = daily_vol * math.sqrt(days_left)
    d = (math.log(spot / strike) - 0.5 * sd * sd) / sd
    return normal_cdf(d)


def taker_fee(price: float, contracts: int = 1, rate: float = 0.07) -> float:
    """Kalshi's taker fee in dollars: rate * C * P * (1 - P), rounded up to the cent.

    Check Kalshi's fee schedule for the current rate on gold markets.
    """
    raw = rate * contracts * price * (1.0 - price)
    return math.ceil(round(raw * 100, 6)) / 100.0


@dataclass
class Signal:
    ticker: str
    strike: float
    strike_type: str
    model_prob: float  # our chance that YES wins
    yes_ask: float | None
    no_ask: float | None
    side: str | None  # "YES", "NO", or None
    price: float | None  # what we'd pay per contract
    edge: float | None  # expected profit per contract after fees, in dollars


def yes_probability(strike_type: str, floor: float | None, cap: float | None,
                    spot: float, daily_vol: float, days_left: float) -> float | None:
    """Chance YES wins for the common Kalshi strike types. None if unsupported."""
    if strike_type in ("greater", "greater_or_equal") and floor is not None:
        return prob_above(spot, floor, daily_vol, days_left)
    if strike_type in ("less", "less_or_equal") and cap is not None:
        return 1.0 - prob_above(spot, cap, daily_vol, days_left)
    if strike_type == "between" and floor is not None and cap is not None:
        return prob_above(spot, floor, daily_vol, days_left) - prob_above(spot, cap, daily_vol, days_left)
    return None


def best_trade(ticker: str, strike: float, strike_type: str, p_yes: float,
               yes_ask: float | None, no_ask: float | None,
               min_edge: float, fee_rate: float = 0.07) -> Signal:
    """Pick YES or NO if either looks underpriced by at least `min_edge` after fees."""
    options = []
    if yes_ask is not None and 0 < yes_ask < 1:
        options.append(("YES", yes_ask, p_yes - yes_ask - taker_fee(yes_ask, rate=fee_rate)))
    if no_ask is not None and 0 < no_ask < 1:
        options.append(("NO", no_ask, (1 - p_yes) - no_ask - taker_fee(no_ask, rate=fee_rate)))
    side = price = edge = None
    if options:
        s, pr, e = max(options, key=lambda o: o[2])
        edge = e
        if e >= min_edge:
            side, price = s, pr
    return Signal(ticker, strike, strike_type, p_yes, yes_ask, no_ask, side, price, edge)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
