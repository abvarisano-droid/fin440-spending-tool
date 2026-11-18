"""Hand checks for core/lab.py (no network)."""

import numpy as np
import pandas as pd
import pytest

from core import lab


def _px(values, start="2026-01-02"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_constant_mix_single_ticker_is_price_relative():
    a = _px([100, 110, 99, 120])
    idx = lab.constant_mix_index({"A": a}, {"A": 1.0})
    assert idx.tolist() == pytest.approx([1.0, 1.1, 0.99, 1.2])


def test_constant_mix_50_50_hand():
    # A: +10% then -10%; B: 0% then +20%. Mix: +5%, then +5% -> 1.05 * 1.05 = 1.1025
    a = _px([100, 110, 99])
    b = _px([50, 50, 60])
    idx = lab.constant_mix_index({"A": a, "B": b}, {"A": 0.5, "B": 0.5})
    assert idx.tolist() == pytest.approx([1.0, 1.05, 1.1025])


def test_market_against_itself_sits_on_the_sml():
    rng = np.random.default_rng(1)
    mkt = _px(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 300)))
    t = lab.risk_table({"SPY": mkt}, mkt, 0.04).iloc[0]
    assert t["beta"] == pytest.approx(1.0)
    assert t["alpha_annual"] == pytest.approx(0.0, abs=1e-12)
    assert t["r_squared"] == pytest.approx(1.0)
    assert t["sml_gap"] == pytest.approx(0.0, abs=1e-12)
    assert lab.market_annual_return(mkt, mkt.index) == pytest.approx(t["ann_return"])


def test_tickers_for_dedupes_and_adds_market():
    assert lab.tickers_for(["100% VOO", "60/40 VOO/BND"], ("SPY",)) == ["VOO", "BND", "SPY"]
