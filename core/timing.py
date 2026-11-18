"""Market timing test: is your real spending calendar luckier than random?

Why this is an efficient-markets test: if prices already reflect what is knowable, the
dates you happened to spend on carry no information about future prices. Then your real
timing should look like a typical random draw: if we keep your purchase amounts but
scatter them over random trading days in the same window, your actual result should land
near the 50th percentile of those scattered results. Anything from about the 5th to the
95th percentile is consistent with luck. A result far outside that range would suggest
your timing carried information (or a very unusual run of luck).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def timing_test(spend: pd.DataFrame, prices: pd.Series, n_shuffles: int = 1000, seed: int = 0) -> dict:
    """Reassign each purchase to a uniformly random trading day between the first and last
    actual buy dates (inclusive), `n_shuffles` times, and value each at the latest price
    exactly as `build_shadow` does (shares = amount / price, value = shares * last price)."""
    prices = prices.dropna().sort_index()
    if prices.empty:
        raise ValueError("No prices available for this ticker and date range.")
    idx = prices.index
    pos = idx.searchsorted(spend["date"].values, side="left")
    ok = pos < len(idx)
    if not ok.any():
        raise ValueError("No purchases fall within the price history.")

    amounts = spend["amount"].to_numpy(dtype=float)[ok]
    p = prices.to_numpy(dtype=float)
    last = p[-1]
    pos = pos[ok]
    lo, hi = int(pos.min()), int(pos.max())

    actual = float((amounts / p[pos]).sum() * last)
    rng = np.random.default_rng(seed)
    draws = rng.integers(lo, hi + 1, size=(n_shuffles, len(amounts)))
    shuffled = (amounts / p[draws]).sum(axis=1) * last

    tie = np.abs(shuffled - actual) <= 1e-12 * abs(actual)
    below = (shuffled < actual) & ~tie
    percentile = float(below.mean() + 0.5 * tie.mean())

    return {
        "actual_value": actual,
        "shuffled_values": shuffled,
        "percentile": percentile,
        "median_shuffled": float(np.median(shuffled)),
        "p_value_two_sided": 2 * min(percentile, 1 - percentile),
        "lump_sum_value": float(amounts.sum() / p[lo] * last),
        "n_shuffles": n_shuffles,
        "seed": seed,
        "trading_days_used": hi - lo + 1,
    }
