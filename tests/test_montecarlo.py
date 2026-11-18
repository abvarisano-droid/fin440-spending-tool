"""Monte Carlo tests. Expected values come from tvm (verified against Excel) or by hand."""

import time

import numpy as np
import pandas as pd
import pytest

from core import montecarlo as mc
from core import tvm


def _tvm_final(age0, age1, pmt, rate, start=0.0, due=False):
    return tvm.roth_projection(age0, age1, pmt, rate, start, "apr", due).iloc[-1]["balance"]


@pytest.mark.parametrize(
    "age0,age1,pmt,start,due",
    [
        (21, 65, 200, 0.0, False),
        (21, 65, 200, 1500.0, True),
        # 45 to 55 at $700/month: cap is 7500/12 = 625 for ages 45-49, and
        # (7500+1100)/12 = 716.67 > 700 so 700 applies for ages 50-54.
        (45, 55, 700, 0.0, False),
        (45, 55, 700, 2000.0, True),
    ],
)
def test_zero_vol_matches_tvm(age0, age1, pmt, start, due):
    res = mc.simulate_roth(age0, age1, pmt, start, annual_vol=0.0, annual_mean=0.07, n_sims=50, due=due)
    expected = _tvm_final(age0, age1, pmt, 0.07, start, due)
    assert np.allclose(res["final"], expected, rtol=1e-10)
    p = res["percentiles"]
    assert np.allclose(p["p5"], p["p95"], rtol=1e-12)
    tv = tvm.roth_projection(age0, age1, pmt, 0.07, start, "apr", due)
    assert np.allclose(p["p50"].to_numpy(), tv["balance"].to_numpy(), rtol=1e-10)
    assert list(res["ages"]) == list(tv["age"])
    assert res["total_contributed"] == pytest.approx(tv["total_contributed"].iloc[-1])


def test_catchup_payment_total():
    res = mc.simulate_roth(45, 55, 700, annual_vol=0.0)
    assert res["total_contributed"] == pytest.approx(625 * 60 + 700 * 60)


def test_mean_matches_closed_form():
    res = mc.simulate_roth(21, 65, 200, annual_mean=0.07, annual_vol=0.15, n_sims=20000, seed=1)
    expected = mc.expected_fv_closed_form(21, 65, 200, 0.0, 0.07)
    assert res["mean_final"] == pytest.approx(expected, rel=0.01)


def test_closed_form_equals_tvm():
    assert mc.expected_fv_closed_form(21, 65, 200, 0.0, 0.07) == pytest.approx(
        _tvm_final(21, 65, 200, 0.07), rel=1e-10
    )


def test_percentiles_monotone():
    res = mc.simulate_roth(30, 60, 400, 1000.0, n_sims=2000, seed=3)
    p = res["percentiles"]
    assert list(p.columns) == ["p5", "p25", "p50", "p75", "p95"]
    assert (p["p5"] <= p["p25"]).all() and (p["p25"] <= p["p50"]).all()
    assert (p["p50"] <= p["p75"]).all() and (p["p75"] <= p["p95"]).all()
    assert (res["final"] >= 0).all()


def test_bootstrap_constant_history():
    res = mc.simulate_roth(21, 65, 200, method="bootstrap", history=np.full(24, 0.005), n_sims=20)
    assert np.allclose(res["final"], _tvm_final(21, 65, 200, 0.06), rtol=1e-10)


def test_bootstrap_validation():
    with pytest.raises(ValueError):
        mc.simulate_roth(21, 65, 200, method="bootstrap", history=None)
    with pytest.raises(ValueError):
        mc.simulate_roth(21, 65, 200, method="bootstrap", history=np.zeros(11))


def test_prob_reaching():
    assert mc.prob_reaching(np.array([1, 2, 3, 4]), 3) == 0.5


def test_seed_reproducible():
    a = mc.simulate_roth(21, 65, 200, n_sims=500, seed=7)
    b = mc.simulate_roth(21, 65, 200, n_sims=500, seed=7)
    c = mc.simulate_roth(21, 65, 200, n_sims=500, seed=8)
    assert np.array_equal(a["final"], b["final"])
    assert not np.array_equal(a["final"], c["final"])


def test_monthly_returns_from_prices():
    idx = pd.to_datetime(["2024-01-15", "2024-01-31", "2024-02-10", "2024-02-29", "2024-03-05", "2024-03-28"])
    prices = pd.Series([100.0, 110.0, 120.0, 121.0, 125.0, 133.1], index=idx)
    # Month-end last prices: Jan 110, Feb 121, Mar 133.1 -> returns 0.10 and 0.10.
    out = mc.monthly_returns_from_prices(prices)
    assert len(out) == 2
    assert np.allclose(out.to_numpy(), [0.10, 0.10])


def test_speed_44_years():
    t = time.perf_counter()
    mc.simulate_roth(21, 65, 200, n_sims=5000, seed=0)
    assert time.perf_counter() - t < 2.0
