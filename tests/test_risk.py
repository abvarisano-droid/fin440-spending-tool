import math

import pandas as pd
import pytest

from core import risk


def _idx(n, freq="B"):
    return pd.date_range("2024-01-01", periods=n, freq=freq)


MKT = [0.01, -0.02, 0.03, 0.00, 0.02, -0.01]


def test_beta_two_times_market():
    # asset = 2 * market, rf = 0: slope exactly 2, intercept 0, perfect fit.
    idx = _idx(6)
    m = pd.Series(MKT, index=idx)
    out = risk.beta_alpha(2 * m, m, 0.0, 252)
    assert out["beta"] == pytest.approx(2.0)
    assert out["alpha_annual"] == pytest.approx(0.0, abs=1e-12)
    assert out["r_squared"] == pytest.approx(1.0)
    assert out["n"] == 6


def test_alpha_constant():
    # asset = 0.5 * market + 0.001: slope 0.5, intercept 0.001 per period.
    idx = _idx(6)
    m = pd.Series(MKT, index=idx)
    out = risk.beta_alpha(0.5 * m + 0.001, m, 0.0, 12)
    assert out["beta"] == pytest.approx(0.5)
    assert out["alpha_period"] == pytest.approx(0.001)
    assert out["alpha_annual"] == pytest.approx(0.012)  # 0.001 * 12


def test_beta_alpha_errors():
    idx = _idx(5)
    m = pd.Series([0.01] * 5, index=idx)
    a = pd.Series(MKT[:5], index=idx)
    with pytest.raises(ValueError):
        risk.beta_alpha(a, m, 0.0, 12)  # zero market variance
    with pytest.raises(ValueError):
        risk.beta_alpha(a.iloc[:2], a.iloc[:2], 0.0, 12)  # too few points


def test_max_drawdown():
    # Peak 130, trough 65: 65 / 130 - 1 = -0.5. (120 -> 90 is only -0.25.)
    idx = _idx(6)
    v = pd.Series([100, 120, 90, 130, 65, 70], index=idx, dtype=float)
    mdd, peak, trough = risk.max_drawdown(v)
    assert mdd == pytest.approx(-0.5)
    assert peak == idx[3]
    assert trough == idx[4]


def test_max_drawdown_never_falls():
    idx = _idx(3)
    mdd, p, t = risk.max_drawdown(pd.Series([1.0, 2.0, 3.0], index=idx))
    assert (mdd, p, t) == (0.0, idx[0], idx[0])


def test_annualized_vol_by_hand():
    # mean 0; squared deviations sum 4 * 0.0001 = 0.0004; /(n-1 = 3) = 0.000133333;
    # sample std = 0.0115470; times sqrt(12) = sqrt(0.0004/3*12) = sqrt(0.0016) = 0.04.
    r = pd.Series([0.01, -0.01, 0.01, -0.01])
    assert risk.annualized_vol(r, 12) == pytest.approx(0.04)


def test_annualized_return_compounding():
    r = pd.Series([0.01] * 12)
    assert risk.annualized_return(r, 12) == pytest.approx(1.01 ** 12 - 1)


def test_sharpe_constant_returns_is_nan():
    r = pd.Series([0.01] * 10)
    assert math.isnan(risk.sharpe_ratio(r, 0.0, 12))


def test_sharpe_by_hand():
    # rf = 0, ppy = 12, returns [0.02, 0.00, 0.02, 0.00]: mean 0.01,
    # sample var = 4 * 0.0001 / 3, std = 0.0115470; Sharpe = 0.01*12 / (0.011547*sqrt(12))
    # = 0.12 / 0.04 = 3.0.
    r = pd.Series([0.02, 0.0, 0.02, 0.0])
    assert risk.sharpe_ratio(r, 0.0, 12) == pytest.approx(3.0)


def test_capm_expected_return():
    # 0.04 + 1.5 * (0.10 - 0.04) = 0.04 + 0.09 = 0.13
    assert risk.capm_expected_return(0.04, 1.5, 0.10) == pytest.approx(0.13)


def test_sml_line():
    df = risk.sml_line(0.04, 0.10)
    assert list(df.columns) == ["beta", "expected_return"]
    assert len(df) == 21
    assert df["expected_return"].iloc[0] == pytest.approx(0.04)   # beta 0
    assert df["expected_return"].iloc[10] == pytest.approx(0.10)  # beta 1
    assert df["expected_return"].iloc[20] == pytest.approx(0.16)  # beta 2


def test_periods_per_year():
    assert risk.periods_per_year(pd.bdate_range("2024-01-01", periods=60)) == 252
    assert risk.periods_per_year(pd.date_range("2024-01-31", periods=12, freq="ME")) == 12
    assert risk.periods_per_year(pd.date_range("2024-01-01", periods=20, freq="W")) == 52


def test_leading_zeros_dropped():
    idx = _idx(5)
    v = pd.Series([0.0, 0.0, 100.0, 110.0, 99.0], index=idx)
    r = risk.simple_returns(v)
    # 110/100 - 1 = 0.10; 99/110 - 1 = -0.10
    assert list(r.round(10)) == [0.1, -0.1]
    mdd, peak, trough = risk.max_drawdown(v)
    assert mdd == pytest.approx(-0.1)
    assert peak == idx[3] and trough == idx[4]


def test_risk_summary_runs():
    idx = _idx(7, "ME")
    m = pd.Series([100, 101, 99, 103, 104, 102, 106], index=idx, dtype=float)
    a = pd.Series([0, 50, 49.5, 52, 51, 53, 52.5], index=idx, dtype=float)
    s = risk.risk_summary(a, m, 0.03)
    assert s["ppy"] == 12
    assert s["n"] == 5
    assert s["max_drawdown"] <= 0
