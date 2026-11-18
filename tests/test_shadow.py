import pandas as pd
import pytest

from core.shadow import build_shadow, xirr


def _prices():
    # trading days only: Fri 1/2, Mon 1/5, Tue 1/6 ... with a weekend gap
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-12-31"])
    return pd.Series([100.0, 110.0, 120.0, 150.0], index=idx)


def _spend(rows):
    return pd.DataFrame(rows, columns=["date", "description", "amount"]).assign(
        date=lambda d: pd.to_datetime(d["date"])
    )


def test_weekend_rolls_forward_and_values_by_hand():
    spend = _spend([
        ("2026-01-02", "A", 100.0),  # buys 1 share @100
        ("2026-01-03", "B", 110.0),  # Saturday -> Mon 1/5 @110 -> 1 share
        ("2026-01-06", "C", 60.0),   # @120 -> 0.5 share
    ])
    res = build_shadow(spend, _prices())
    assert list(res.ledger["buy_date"].dt.strftime("%Y-%m-%d")) == ["2026-01-02", "2026-01-05", "2026-01-06"]
    assert res.ledger["shares"].tolist() == pytest.approx([1.0, 1.0, 0.5])
    # 2.5 shares * 150 = 375 ; invested 270 ; gain 105
    assert res.invested == pytest.approx(270)
    assert res.value == pytest.approx(375)
    assert res.gain == pytest.approx(105)
    assert res.simple_return == pytest.approx(105 / 270)
    assert res.skipped == 0
    assert res.timeline["value"].iloc[-1] == pytest.approx(375)
    assert res.timeline["invested"].iloc[-1] == pytest.approx(270)


def test_purchase_after_last_price_is_skipped():
    spend = _spend([("2026-01-02", "A", 100.0), ("2027-01-04", "Late", 50.0)])
    res = build_shadow(spend, _prices())
    assert res.skipped == 1
    assert res.invested == pytest.approx(100)


def test_xirr_one_year_ten_percent():
    # -100 on day 0, +110 exactly 365 days later -> 10%
    flows = [(pd.Timestamp("2025-01-01"), -100.0), (pd.Timestamp("2026-01-01"), 110.0)]
    assert xirr(flows) == pytest.approx(0.10, abs=1e-8)


def test_xirr_short_span_is_none():
    flows = [(pd.Timestamp("2026-01-01"), -100.0), (pd.Timestamp("2026-01-03"), 101.0)]
    assert xirr(flows) is None
