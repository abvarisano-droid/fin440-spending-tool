import time

import numpy as np
import pandas as pd
import pytest

from core.shadow import build_shadow
from core.timing import timing_test


def _prices(vals, start="2024-01-01"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype=float)


def _spend(dates, amounts):
    return pd.DataFrame({"date": pd.to_datetime(dates), "description": "x", "amount": amounts})


def test_constant_prices_all_equal_percentile_half():
    # price 10 everywhere: value = total / 10 * 10 = 60 for every arrangement
    p = _prices([10.0] * 30)
    spend = _spend(["2024-01-02", "2024-01-10", "2024-01-22"], [10.0, 20.0, 30.0])
    r = timing_test(spend, p, n_shuffles=200)
    assert r["actual_value"] == pytest.approx(60.0)
    assert np.allclose(r["shuffled_values"], 60.0)
    assert r["percentile"] == 0.5
    assert r["p_value_two_sided"] == 1.0


def test_rising_prices_lump_sum_beats_all_shuffles():
    p = _prices(list(range(100, 160)))
    spend = _spend(["2024-01-02", "2024-01-15", "2024-02-12", "2024-03-01"], [10.0, 20.0, 30.0, 40.0])
    r = timing_test(spend, p, n_shuffles=500)
    assert r["lump_sum_value"] >= r["shuffled_values"].max() - 1e-9
    assert r["lump_sum_value"] >= r["actual_value"]
    # lump: $100 at the first buy day's price (Jan 2 is bday index 1, price 101), last price 159
    # -> 100 / 101 * 159
    assert r["lump_sum_value"] == pytest.approx(100 / 101 * 159)


def test_actual_matches_build_shadow():
    rng = np.random.default_rng(1)
    p = _prices(100 + rng.normal(0, 1, 120).cumsum())
    spend = _spend(["2024-01-06", "2024-02-03", "2024-03-09"], [12.5, 40.0, 7.25])  # weekends roll
    r = timing_test(spend, p)
    assert r["actual_value"] == pytest.approx(build_shadow(spend, p).value, rel=1e-12)


def test_same_seed_same_shuffles():
    rng = np.random.default_rng(2)
    p = _prices(100 + rng.normal(0, 1, 80).cumsum())
    spend = _spend(["2024-01-02", "2024-02-01", "2024-03-01"], [10.0, 20.0, 30.0])
    a = timing_test(spend, p, n_shuffles=100, seed=5)
    b = timing_test(spend, p, n_shuffles=100, seed=5)
    c = timing_test(spend, p, n_shuffles=100, seed=6)
    assert np.array_equal(a["shuffled_values"], b["shuffled_values"])
    assert not np.array_equal(a["shuffled_values"], c["shuffled_values"])


def test_trading_days_used_and_pvalue():
    p = _prices([10.0, 11.0, 12.0, 13.0, 14.0])
    spend = _spend(["2024-01-02", "2024-01-04"], [10.0, 10.0])  # index 1..3 -> 3 days
    r = timing_test(spend, p, n_shuffles=50)
    assert r["trading_days_used"] == 3
    assert r["p_value_two_sided"] == pytest.approx(2 * min(r["percentile"], 1 - r["percentile"]))


def test_speed_260_purchases():
    rng = np.random.default_rng(3)
    p = _prices(100 + rng.normal(0, 1, 400).cumsum().clip(-50))
    spend = _spend(p.index[:260], rng.uniform(5, 50, 260))
    t = time.perf_counter()
    timing_test(spend, p, n_shuffles=1000)
    assert time.perf_counter() - t < 1.0
