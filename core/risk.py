"""Risk and CAPM math. Pure functions on pandas Series (tz-naive date index).

Conventions used everywhere in this module:
- Returns are simple (arithmetic) per-period returns, r_t = V_t / V_{t-1} - 1.
- ppy is periods per year (252 daily, 52 weekly, 12 monthly).
- A per-period risk-free rate is the compounded equivalent of the annual rate:
  rf_period = (1 + rf_annual)^(1/ppy) - 1.
- Standard deviations and covariances are sample statistics (ddof=1).

Caveat: a portfolio that receives new cash (contributions) has a value series whose
percentage changes are NOT investment returns, because the jump from a deposit looks like
a gain. Callers must pass a price-like series (for example value per share, or the
adjusted close of a fund), not a balance that includes deposits. This module does not try
to fix that.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _strip_leading_zeros(values: pd.Series) -> pd.Series:
    """Drop NaNs and any leading zero values (a shadow portfolio before its first buy)."""
    v = values.dropna()
    nonzero = np.flatnonzero(v.to_numpy() != 0)
    if len(nonzero) == 0:
        return v.iloc[0:0]
    return v.iloc[nonzero[0]:]


def simple_returns(values: pd.Series) -> pd.Series:
    """Simple per-period returns: r_t = V_t / V_{t-1} - 1.

    Leading zeros (value before the first purchase) are dropped first so there is no
    division by zero. The first observation has no prior value, so it is dropped too.
    """
    v = _strip_leading_zeros(values)
    return v.pct_change().dropna()


def periods_per_year(index: pd.DatetimeIndex) -> int:
    """Observations per year inferred from the median gap between dates.

    Median gap <= 4 days gives 252 (daily trading data), <= 8 days gives 52 (weekly),
    otherwise 12 (monthly). Fewer than 2 dates defaults to 12.
    """
    if len(index) < 2:
        return 12
    gap = pd.Series(pd.DatetimeIndex(index)).diff().dropna().median() / pd.Timedelta(days=1)
    if gap <= 4:
        return 252
    if gap <= 8:
        return 52
    return 12


def annualized_return(returns: pd.Series, ppy: int) -> float:
    """Geometric annualized return: (prod(1 + r_t))^(ppy / n) - 1, n = number of returns."""
    n = len(returns)
    if n == 0:
        return float("nan")
    growth = float(np.prod(1.0 + returns.to_numpy(dtype=float)))
    if growth <= 0:
        return -1.0
    return growth ** (ppy / n) - 1.0


def annualized_vol(returns: pd.Series, ppy: int) -> float:
    """Annualized volatility: sample std of per-period returns (ddof=1) times sqrt(ppy)."""
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * math.sqrt(ppy))


def sharpe_ratio(returns: pd.Series, rf_annual: float, ppy: int) -> float:
    """Annualized Sharpe ratio.

    rf_period = (1 + rf_annual)^(1/ppy) - 1; excess_t = r_t - rf_period;
    Sharpe = mean(excess) * ppy / (std(excess, ddof=1) * sqrt(ppy)).
    Returns nan when the excess-return std is zero (or there are fewer than 2 returns).
    """
    if len(returns) < 2:
        return float("nan")
    rf_p = (1.0 + rf_annual) ** (1.0 / ppy) - 1.0
    excess = returns - rf_p
    sd = float(excess.std(ddof=1))
    if not np.isfinite(sd) or math.isclose(sd, 0.0, abs_tol=1e-14):
        return float("nan")
    return float(excess.mean() * ppy / (sd * math.sqrt(ppy)))


def max_drawdown(values: pd.Series) -> tuple[float, pd.Timestamp, pd.Timestamp]:
    """Maximum drawdown: the most negative value of V_t / max(V_s, s <= t) - 1.

    Returns (drawdown as a negative fraction, peak date, trough date). The peak date is
    the date of the highest value at or before the trough. If the series never falls
    below a prior peak, returns (0.0, first date, first date).
    """
    v = _strip_leading_zeros(values)
    if v.empty:
        raise ValueError("no non-zero values")
    dd = v / v.cummax() - 1.0
    trough = dd.idxmin()
    mdd = float(dd.loc[trough])
    if mdd >= 0:
        return 0.0, v.index[0], v.index[0]
    peak = v.loc[:trough].idxmax()
    return mdd, peak, trough


def beta_alpha(asset_returns: pd.Series, market_returns: pd.Series,
               rf_annual: float, ppy: int) -> dict:
    """CAPM regression of asset excess returns on market excess returns (OLS).

    Inner-join on common dates, subtract rf_period = (1 + rf_annual)^(1/ppy) - 1 from
    both, then with a = asset excess and m = market excess:
      beta         = cov(a, m) / var(m)            (ddof=1 on both)
      alpha_period = mean(a) - beta * mean(m)
      alpha_annual = alpha_period * ppy            (simple, arithmetic annualization
                                                    of Jensen's alpha, not compounded)
      r_squared    = corr(a, m)^2
    Returns a dict with beta, alpha_period, alpha_annual, r_squared and n (observations).
    Raises ValueError with fewer than 3 common observations or zero market variance.
    """
    df = pd.concat([asset_returns.rename("a"), market_returns.rename("m")],
                   axis=1, join="inner").dropna()
    n = len(df)
    if n < 3:
        raise ValueError(f"need at least 3 common observations, got {n}")
    rf_p = (1.0 + rf_annual) ** (1.0 / ppy) - 1.0
    a = df["a"] - rf_p
    m = df["m"] - rf_p
    var_m = float(m.var(ddof=1))
    if math.isclose(var_m, 0.0, abs_tol=1e-18):
        raise ValueError("market variance is zero")
    beta = float(a.cov(m) / var_m)
    alpha_p = float(a.mean() - beta * m.mean())
    sd_a = float(a.std(ddof=1))
    if math.isclose(sd_a, 0.0, abs_tol=1e-18):
        r2 = float("nan")
    else:
        r2 = float(a.corr(m) ** 2)
    return {"beta": beta, "alpha_period": alpha_p, "alpha_annual": alpha_p * ppy,
            "r_squared": r2, "n": n}


def capm_expected_return(rf_annual: float, beta: float, market_return_annual: float) -> float:
    """CAPM expected return: E[R] = rf + beta * (E[Rm] - rf), all annual."""
    return rf_annual + beta * (market_return_annual - rf_annual)


def sml_line(rf_annual: float, market_return_annual: float, betas=None) -> pd.DataFrame:
    """Security market line: expected_return = rf + beta * (E[Rm] - rf) for each beta.

    betas defaults to numpy.linspace(0, 2, 21). Columns: beta, expected_return.
    """
    if betas is None:
        betas = np.linspace(0, 2, 21)
    betas = np.asarray(list(betas), dtype=float)
    return pd.DataFrame({
        "beta": betas,
        "expected_return": rf_annual + betas * (market_return_annual - rf_annual),
    })


def risk_summary(values: pd.Series, market_values: pd.Series, rf_annual: float) -> dict:
    """One-call summary for an asset value series against a market value series.

    Builds simple returns from both (leading zeros dropped), takes ppy from the asset's
    index, and reports: ann_return and ann_vol (asset), sharpe, max_drawdown (float),
    mdd_peak, mdd_trough, beta, alpha_annual, r_squared, capm_expected (CAPM expected
    return using the market's own geometric annualized return over the dates it shares
    with the asset), n (common observations in the regression) and ppy.
    Inputs must be price-like series (see module docstring).
    """
    r_a = simple_returns(values)
    r_m = simple_returns(market_values)
    ppy = periods_per_year(values.dropna().index)
    mdd, peak, trough = max_drawdown(values)
    ba = beta_alpha(r_a, r_m, rf_annual, ppy)
    common = r_a.index.intersection(r_m.index)
    mkt_ann = annualized_return(r_m.loc[common], ppy)
    return {
        "ann_return": annualized_return(r_a, ppy),
        "ann_vol": annualized_vol(r_a, ppy),
        "sharpe": sharpe_ratio(r_a, rf_annual, ppy),
        "max_drawdown": mdd,
        "mdd_peak": peak,
        "mdd_trough": trough,
        "beta": ba["beta"],
        "alpha_annual": ba["alpha_annual"],
        "r_squared": ba["r_squared"],
        "capm_expected": capm_expected_return(rf_annual, ba["beta"], mkt_ann),
        "n": ba["n"],
        "ppy": ppy,
    }
