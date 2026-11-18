import pandas as pd
import pytest

from core.portfolios import PRESETS, build_portfolio
from core.shadow import build_shadow


def _spend(dates, amounts):
    return pd.DataFrame({"date": pd.to_datetime(dates), "description": "x", "amount": amounts})


def _prices(vals, start="2024-01-01"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype=float)


def test_presets_sum_to_one():
    for w in PRESETS.values():
        assert sum(w.values()) == pytest.approx(1.0)


def test_single_fund_matches_build_shadow():
    p = _prices([100 + i for i in range(60)])
    spend = _spend(["2024-01-02", "2024-01-20", "2024-02-10"], [50.0, 30.0, 20.0])
    ref = build_shadow(spend, p)
    got = build_portfolio(spend, {"A": p}, {"A": 1.0})
    assert got.invested == pytest.approx(ref.invested, rel=1e-12)
    assert got.value == pytest.approx(ref.value, rel=1e-12)
    assert got.xirr == pytest.approx(ref.xirr, rel=1e-9)


def test_scaled_fund_prices_scale_out():
    # B = 2 * A. For $a split 50/50: shares = a/2/p + a/2/(2p); value at last price P
    # = a/2 * P/p + a/2 * P/p = a * P/p, the same as 100% A.
    a = _prices([100, 105, 98, 110, 120, 115, 130, 125, 140, 150])
    b = a * 2
    spend = _spend(["2024-01-01", "2024-01-04", "2024-01-09"], [100.0, 200.0, 50.0])
    one = build_portfolio(spend, {"A": a}, {"A": 1.0})
    mix = build_portfolio(spend, {"A": a, "B": b}, {"A": 0.5, "B": 0.5})
    assert mix.value == pytest.approx(one.value, rel=1e-12)
    assert mix.invested == pytest.approx(one.invested, rel=1e-12)


def test_bad_weights_raise():
    p = _prices([100, 101, 102])
    spend = _spend(["2024-01-01"], [10.0])
    with pytest.raises(ValueError):
        build_portfolio(spend, {"A": p}, {"A": 0.9})
    with pytest.raises(ValueError):
        build_portfolio(spend, {"A": p, "B": p}, {"A": 1.2, "B": -0.2})


def test_unit_value_flat_with_constant_prices():
    p = _prices([50.0] * 10)
    spend = _spend(["2024-01-01", "2024-01-03", "2024-01-08"], [100.0, 40.0, 60.0])
    res = build_portfolio(spend, {"A": p}, {"A": 1.0})
    assert (res.unit_value == 1.0).all()


def test_unit_value_hand_case():
    # prices 100, 110, 121; buy $100 on day 1 and day 2.
    # day1: 1 share, unit price 1.0, units 100. day2: pre-purchase value 1*110 = 110,
    # unit price 110/100 = 1.1, new units 100/1.1 = 90.909. day3: shares 1 + 100/110,
    # value 1.909091*121 = 231, units 190.909, unit price 231/190.909 = 1.21.
    p = _prices([100.0, 110.0, 121.0])
    spend = _spend(["2024-01-01", "2024-01-02"], [100.0, 100.0])
    res = build_portfolio(spend, {"A": p}, {"A": 1.0})
    assert res.unit_value.tolist() == pytest.approx([1.0, 1.1, 1.21], rel=1e-12)
    assert res.timeline["invested"].tolist() == [100.0, 200.0, 200.0]


def test_common_index_and_skipped():
    a = _prices([100, 101, 102, 103, 104])
    b = a.drop(a.index[1])  # B has no Jan 2
    spend = _spend(["2024-01-02", "2024-02-01"], [100.0, 10.0])
    res = build_portfolio(spend, {"A": a, "B": b}, {"A": 0.5, "B": 0.5})
    assert res.skipped == 1
    assert res.invested == pytest.approx(100.0)
    assert res.name == ""
