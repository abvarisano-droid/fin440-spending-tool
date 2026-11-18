"""Multi-fund shadow portfolios: split each purchase across funds by fixed weights.

Rules: buy-and-hold, no rebalancing, no fees. Every slice of a purchase buys on the same
day: the first trading day on or after the purchase date that exists in ALL the portfolio's
price series (the intersection of their indexes). Each ticker is valued by `build_shadow`
on its weighted share of the spend, then the pieces are summed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.shadow import build_shadow, xirr

PRESETS: dict[str, dict[str, float]] = {
    "100% VOO": {"VOO": 1.0},
    "60/40 VOO/BND": {"VOO": 0.6, "BND": 0.4},
    "100% BND": {"BND": 1.0},
    "100% QQQ": {"QQQ": 1.0},
}


@dataclass
class PortfolioResult:
    weights: dict[str, float]
    invested: float
    value: float
    gain: float
    simple_return: float  # gain / invested
    xirr: float | None  # annualized money-weighted return
    timeline: pd.DataFrame  # daily: date, invested, value (summed across tickers)
    unit_value: pd.Series  # time-weighted value per unit, starts at 1.0 (see build_portfolio)
    skipped: int
    as_of: pd.Timestamp
    name: str = field(default="")


def _check_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise ValueError("Weights are empty.")
    if any(not (w > 0) for w in weights.values()):
        raise ValueError("Every weight must be positive.")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Weights must sum to 1.")


def build_portfolio(
    spend: pd.DataFrame, prices: dict[str, pd.Series], weights: dict[str, float], name: str = ""
) -> PortfolioResult:
    """`spend` needs columns date, description, amount. `prices` maps ticker to a daily
    close Series (tz-naive dates). `weights` maps ticker to a positive weight summing to 1.

    `unit_value` is the standard time-weighted return method, the way a mutual fund
    computes its NAV. Units start at the first buy with a unit price of 1.0. On each later
    day, unit price = (portfolio value before that day's purchases) / units outstanding;
    that day's purchases then buy units at that unit price. New cash therefore never moves
    the series, so volatility, beta and drawdown measure the investment, not contributions.
    """
    _check_weights(weights)
    missing = [t for t in weights if t not in prices]
    if missing:
        raise ValueError(f"No prices supplied for: {', '.join(missing)}")

    cleaned = {t: prices[t].dropna().sort_index() for t in weights}
    common = None
    for s in cleaned.values():
        common = s.index if common is None else common.intersection(s.index)
    if common is None or len(common) == 0:
        raise ValueError("The tickers share no trading days.")

    results = {}
    for t, w in weights.items():
        scaled = spend.copy()
        scaled["amount"] = scaled["amount"] * w
        results[t] = build_shadow(scaled, cleaned[t].loc[common])

    first = next(iter(results.values()))
    invested = float(sum(r.invested for r in results.values()))
    value = float(sum(r.value for r in results.values()))
    gain = value - invested

    timeline = first.timeline[["date"]].copy()
    timeline["invested"] = sum(r.timeline["invested"].to_numpy() for r in results.values())
    timeline["value"] = sum(r.timeline["value"].to_numpy() for r in results.values())

    # combined buy-date cash flows plus the final value (same buy dates in every ticker)
    buy_amounts = sum(r.ledger["amount"].to_numpy() for r in results.values())
    flows = [(d, -a) for d, a in zip(first.ledger["buy_date"], buy_amounts)]
    flows.append((first.as_of, value))

    return PortfolioResult(
        name=name,
        weights=dict(weights),
        invested=invested,
        value=value,
        gain=gain,
        simple_return=gain / invested if invested else 0.0,
        xirr=xirr(flows) if invested else None,
        timeline=timeline,
        unit_value=_unit_value(timeline),
        skipped=first.skipped,
        as_of=first.as_of,
    )


def _unit_value(timeline: pd.DataFrame) -> pd.Series:
    inv = timeline["invested"].to_numpy(dtype=float)
    val = timeline["value"].to_numpy(dtype=float)
    if inv.size == 0 or inv[-1] == 0:
        return pd.Series(dtype=float, name="unit_value")
    buy = np.diff(inv, prepend=0.0)
    out = np.empty(len(inv))
    units = 0.0
    for i in range(len(inv)):
        p = 1.0 if units == 0.0 else (val[i] - buy[i]) / units  # value before today's buys
        out[i] = p
        if buy[i] > 0 and p > 0:
            units += buy[i] / p
    return pd.Series(out, index=pd.DatetimeIndex(timeline["date"]), name="unit_value")
