"""Shadow portfolio: what if every dollar spent had bought a fund instead?

Rules:
- Each purchase buys `amount / price` shares at the close of the first trading day on or
  after the transaction date (weekend and holiday buys roll forward).
- Prices are total-return adjusted closes, so dividends are treated as reinvested.
- Purchases after the last available price are left out and reported, not guessed.
- Fractional shares, no fees, no taxes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ShadowResult:
    ledger: pd.DataFrame  # one row per purchase: date, description, amount, buy_date, price, shares
    timeline: pd.DataFrame  # daily: date, invested, value
    invested: float
    value: float
    gain: float
    simple_return: float  # gain / invested
    xirr: float | None  # annualized money-weighted return
    skipped: int  # purchases with no price on or after their date
    as_of: pd.Timestamp


def build_shadow(spend: pd.DataFrame, prices: pd.Series) -> ShadowResult:
    """`spend` needs columns date, description, amount (positive). `prices` is a daily
    close series indexed by tz-naive dates, sorted ascending."""
    prices = prices.dropna().sort_index()
    if prices.empty:
        raise ValueError("No prices available for this ticker and date range.")

    idx = prices.index
    pos = idx.searchsorted(spend["date"].values, side="left")
    ok = pos < len(idx)

    ledger = spend.loc[ok, ["date", "description", "amount"]].copy()
    ledger["buy_date"] = idx[pos[ok]]
    ledger["price"] = prices.values[pos[ok]]
    ledger["shares"] = ledger["amount"] / ledger["price"]
    ledger = ledger.reset_index(drop=True)

    daily_buys = ledger.groupby("buy_date").agg(invested=("amount", "sum"), shares=("shares", "sum"))
    start = ledger["buy_date"].min() if not ledger.empty else idx[-1]
    span = prices.loc[start:]
    daily = daily_buys.reindex(span.index, fill_value=0.0).cumsum()
    timeline = pd.DataFrame(
        {"date": span.index, "invested": daily["invested"].values, "value": daily["shares"].values * span.values}
    )

    invested = float(ledger["amount"].sum())
    value = float(ledger["shares"].sum() * prices.iloc[-1])
    gain = value - invested
    flows = [(d, -a) for d, a in zip(ledger["buy_date"], ledger["amount"])]
    flows.append((idx[-1], value))

    return ShadowResult(
        ledger=ledger,
        timeline=timeline,
        invested=invested,
        value=value,
        gain=gain,
        simple_return=gain / invested if invested else 0.0,
        xirr=xirr(flows) if invested else None,
        skipped=int((~ok).sum()),
        as_of=idx[-1],
    )


def xirr(flows: list[tuple[pd.Timestamp, float]]) -> float | None:
    """Annualized rate r solving sum(cf / (1 + r)^(days/365)) = 0, by bisection.
    Returns None if there is no sign change (rate undefined) or the span is under a week,
    where annualizing would give a meaningless number."""
    if not flows:
        return None
    t0 = min(d for d, _ in flows)
    span_days = (max(d for d, _ in flows) - t0).days
    if span_days < 7:
        return None
    years = np.array([(d - t0).days / 365.0 for d, _ in flows])
    cfs = np.array([c for _, c in flows])

    def npv(r: float) -> float:
        return float(np.sum(cfs / (1 + r) ** years))

    lo, hi = -0.99, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if np.sign(f_lo) == np.sign(f_hi):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9 or hi - lo < 1e-10:
            break
        if np.sign(f_mid) == np.sign(f_lo):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2
