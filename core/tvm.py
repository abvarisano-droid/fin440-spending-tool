"""Time value of money and the Roth IRA projection.

Conventions (shown in the UI too):
- `annual_rate` is either an APR compounded monthly (periodic rate = r / 12, matches Excel
  FV(r/12, n*12, -pmt)) or an effective annual rate (periodic rate = (1 + r)^(1/12) - 1).
- Contributions are monthly, at the end of each month (ordinary annuity) unless `due=True`.
- With a real (after-inflation) return, every output is in today's dollars.
"""

from __future__ import annotations

import pandas as pd

# 2026 IRS limits (IRS Notice 2025-67): $7,500 base, $1,100 catch-up at age 50+.
IRA_LIMIT_2026 = 7_500.0
IRA_CATCHUP_2026 = 1_100.0
CATCHUP_AGE = 50


def periodic_rate(annual_rate: float, periods_per_year: int = 12, convention: str = "apr") -> float:
    if convention == "apr":
        return annual_rate / periods_per_year
    if convention == "effective":
        return (1 + annual_rate) ** (1 / periods_per_year) - 1
    raise ValueError(f"unknown convention {convention!r}")


def fv_lump(pv: float, rate: float, n: int) -> float:
    """Future value of a single sum: PV (1 + r)^n."""
    return pv * (1 + rate) ** n


def fv_annuity(pmt: float, rate: float, n: int, due: bool = False) -> float:
    """Future value of a level annuity: PMT [((1 + r)^n - 1) / r], times (1 + r) if due."""
    if n <= 0:
        return 0.0
    if rate == 0:
        fv = pmt * n
    else:
        fv = pmt * ((1 + rate) ** n - 1) / rate
    return fv * (1 + rate) if due else fv


def annual_limit(age: int) -> float:
    return IRA_LIMIT_2026 + (IRA_CATCHUP_2026 if age >= CATCHUP_AGE else 0.0)


def roth_projection(
    current_age: int,
    retirement_age: int,
    monthly_contribution: float,
    annual_rate: float,
    starting_balance: float = 0.0,
    convention: str = "apr",
    due: bool = False,
    enforce_limit: bool = True,
) -> pd.DataFrame:
    """Month-by-month simulation, summarized by year of age.

    Each age year has 12 monthly contributions. If `enforce_limit`, the monthly amount is
    capped at that age's annual IRA limit / 12 (limit held flat in today's dollars).
    Returns one row per completed year: age (at year end), contributions that year,
    cumulative contributions, balance, cumulative growth.
    """
    if retirement_age <= current_age:
        raise ValueError("Retirement age must be after current age.")
    r = periodic_rate(annual_rate, 12, convention)

    balance = float(starting_balance)
    total_contrib = 0.0
    rows = []
    for age in range(current_age, retirement_age):
        pmt = monthly_contribution
        if enforce_limit:
            pmt = min(pmt, annual_limit(age) / 12)
        year_contrib = 0.0
        for _ in range(12):
            if due:
                balance = (balance + pmt) * (1 + r)
            else:
                balance = balance * (1 + r) + pmt
            year_contrib += pmt
        total_contrib += year_contrib
        rows.append(
            {
                "age": age + 1,
                "contributed_this_year": year_contrib,
                "total_contributed": total_contrib,
                "balance": balance,
                "growth": balance - total_contrib - starting_balance,
            }
        )
    return pd.DataFrame(rows)
