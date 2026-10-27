from datetime import datetime, timezone

from goldbot.model import best_trade, prob_above, taker_fee, trading_days_between, yes_probability
from goldbot.prices import daily_vol_from_closes


def test_at_the_money_is_about_half():
    assert abs(prob_above(4000, 4000, 0.01, 1) - 0.5) < 0.01


def test_far_strikes():
    assert prob_above(4000, 3000, 0.01, 1) > 0.999
    assert prob_above(4000, 5000, 0.01, 1) < 0.001


def test_expired_uses_spot():
    assert prob_above(4001, 4000, 0.01, 0) == 1.0
    assert prob_above(4000, 4000, 0.01, 0) == 0.0


def test_less_and_between_add_up():
    a = yes_probability("greater", 3990, None, 4000, 0.01, 1)
    b = yes_probability("less", None, 3990, 4000, 0.01, 1)
    assert abs(a + b - 1) < 1e-9
    mid = yes_probability("between", 3990, 4010, 4000, 0.01, 1)
    assert 0 < mid < 1


def test_fee_rounds_up_to_cent():
    assert taker_fee(0.50) == 0.02  # 0.07 * 0.25 = 0.0175 -> 0.02
    assert taker_fee(0.50, contracts=100) == 1.75
    assert taker_fee(0.99) == 0.01


def test_weekend_skipped():
    fri = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    mon = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
    assert abs(trading_days_between(fri, mon) - 1.0) < 1e-9


def test_best_trade_flags_cheap_yes():
    s = best_trade("T", 4000, "greater", 0.70, yes_ask=0.55, no_ask=0.47, min_edge=0.05)
    assert s.side == "YES" and s.price == 0.55
    assert abs(s.edge - (0.70 - 0.55 - 0.02)) < 1e-9


def test_best_trade_no_signal_when_fair():
    s = best_trade("T", 4000, "greater", 0.50, yes_ask=0.52, no_ask=0.50, min_edge=0.05)
    assert s.side is None


def test_vol_from_closes():
    assert daily_vol_from_closes([100, 101, 100, 101, 100]) > 0
