"""Monte Carlo projection of the Roth IRA balance.

Same cash-flow model as core/tvm.py (monthly contributions, IRA cap and age-50 catch-up),
but the monthly return is random instead of fixed. Everything is vectorized over simulations;
only the month loop is sequential.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import tvm

MIN_MONTHLY_RETURN = -0.99
PERCENTILES = (5, 25, 50, 75, 95)


def _monthly_payment_vector(
    current_age: int, retirement_age: int, monthly_contribution: float, enforce_limit: bool
) -> np.ndarray:
    if retirement_age <= current_age:
        raise ValueError("Retirement age must be after current age.")
    yearly = tvm.monthly_payments_by_age(current_age, retirement_age, monthly_contribution, enforce_limit)
    return np.repeat(np.asarray(yearly, dtype=float), 12)


def simulate_roth(
    current_age: int,
    retirement_age: int,
    monthly_contribution: float,
    starting_balance: float = 0.0,
    *,
    method: str = "normal",
    annual_mean: float = 0.07,
    annual_vol: float = 0.15,
    history=None,
    n_sims: int = 5000,
    seed: int = 0,
    due: bool = False,
    enforce_limit: bool = True,
) -> dict:
    """Simulate the Roth IRA balance path n_sims times.

    Model:
    - Payments: tvm.monthly_payments_by_age (IRA limit and age-50 catch-up), 12 months per age
      year, the same for every simulation.
    - Monthly simple return r_t:
        method="normal": i.i.d. Normal(annual_mean / 12, annual_vol / sqrt(12)), the arithmetic
          APR convention (matches tvm convention="apr"). Clipped below at -0.99 so a balance
          can never go negative.
        method="bootstrap": r_t drawn i.i.d. with replacement from `history` (1-D array or
          Series of historical monthly simple returns; at least 12 values, else ValueError).
          Also clipped at -0.99.
    - Balance update each month: end of month b = b * (1 + r_t) + pmt; start of month
      (due=True) b = (b + pmt) * (1 + r_t). Starting balance is b_0.
    - Randomness: numpy.random.default_rng(seed), so results are reproducible.

    Returns dict: ages (age at end of each year), percentiles (DataFrame indexed by age with
    p5, p25, p50, p75, p95), final (array of final balances), total_contributed (sum of
    payments, excluding the starting balance), mean_final, n_sims, seed, method.
    """
    if method not in ("normal", "bootstrap"):
        raise ValueError(f"unknown method {method!r}")
    pmts = _monthly_payment_vector(current_age, retirement_age, monthly_contribution, enforce_limit)
    n_months = len(pmts)
    n_years = n_months // 12
    rng = np.random.default_rng(seed)

    if method == "normal":
        rets = rng.normal(annual_mean / 12, annual_vol / np.sqrt(12), size=(n_months, n_sims))
    else:
        if history is None:
            raise ValueError("bootstrap needs a history of monthly returns")
        hist = np.asarray(history, dtype=float).ravel()
        hist = hist[~np.isnan(hist)]
        if len(hist) < 12:
            raise ValueError("bootstrap needs at least 12 monthly returns")
        rets = rng.choice(hist, size=(n_months, n_sims), replace=True)
    rets = np.maximum(rets, MIN_MONTHLY_RETURN)

    bal = np.full(n_sims, float(starting_balance))
    year_end = np.empty((n_years, n_sims))
    for m in range(n_months):
        if due:
            bal = (bal + pmts[m]) * (1.0 + rets[m])
        else:
            bal = bal * (1.0 + rets[m]) + pmts[m]
        if (m + 1) % 12 == 0:
            year_end[(m + 1) // 12 - 1] = bal

    ages = np.arange(current_age + 1, retirement_age + 1)
    pct = np.percentile(year_end, PERCENTILES, axis=1).T
    percentiles = pd.DataFrame(pct, index=pd.Index(ages, name="age"), columns=[f"p{p}" for p in PERCENTILES])
    return {
        "ages": ages,
        "percentiles": percentiles,
        "final": bal,
        "total_contributed": float(pmts.sum()),
        "mean_final": float(bal.mean()),
        "n_sims": n_sims,
        "seed": seed,
        "method": method,
    }


def prob_reaching(final: np.ndarray, target: float) -> float:
    """Share of simulations whose final balance is at or above target (>=)."""
    final = np.asarray(final, dtype=float)
    return float(np.mean(final >= target))


def expected_fv_closed_form(
    current_age: int,
    retirement_age: int,
    monthly_contribution: float,
    starting_balance: float,
    annual_mean: float,
    due: bool = False,
    enforce_limit: bool = True,
) -> float:
    """Deterministic FV at the fixed monthly rate r = annual_mean / 12 (APR convention), via
    tvm.fv_segments.

    Why the Monte Carlo mean should match it: the final balance is linear in the products of
    growth factors, e.g. b_N = b_0 * prod(1 + r_t) + sum_k pmt_k * prod_{t>k}(1 + r_t). With
    independent returns, E[prod(1 + r_t)] = prod E[1 + r_t] = (1 + r)^n, so E[final] equals the
    fixed-rate FV at the mean return. (The -0.99 clip is negligible at sane volatilities.)
    """
    pmts = tvm.monthly_payments_by_age(current_age, retirement_age, monthly_contribution, enforce_limit)
    r = tvm.periodic_rate(annual_mean, 12, "apr")
    return float(tvm.fv_segments(starting_balance, pmts, r, due)[0])


def monthly_returns_from_prices(prices: pd.Series) -> pd.Series:
    """Month-end simple returns from a price series with a DatetimeIndex: take the last price
    of each calendar month ("ME" resample), pct_change, drop the leading NaN. The first
    (possibly partial) month only serves as the base price. A partial final month is dropped, so
    every sample is a full month: the series counts as partial when it ends more than 4 calendar
    days before month end (a weekend plus a market holiday, like Good Friday, is at most 4)."""
    rets = prices.resample("ME").last().pct_change().dropna()
    if len(prices) and len(rets):
        last = prices.index[-1]
        if ((last + pd.offsets.MonthEnd(0)) - last).days > 4:
            rets = rets.iloc[:-1]
    return rets
