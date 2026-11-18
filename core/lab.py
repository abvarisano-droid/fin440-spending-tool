"""Glue between the math engines and the lab pages: preset portfolios, fund-history mixes and
the risk table. Pure functions; prices are passed in, nothing is fetched here."""

from __future__ import annotations

import pandas as pd

from core import risk
from core.portfolios import PRESETS, PortfolioResult, build_portfolio


def tickers_for(names: list[str], extra: tuple[str, ...] = ()) -> list[str]:
    """Every ticker the named presets need, plus any extras (e.g. the market proxy)."""
    out: list[str] = []
    for n in names:
        out += list(PRESETS[n])
    return list(dict.fromkeys(out + list(extra)))


def preset_portfolios(spend: pd.DataFrame, prices: dict[str, pd.Series],
                      names: list[str]) -> dict[str, PortfolioResult]:
    """Build each named preset on the same purchases."""
    return {n: build_portfolio(spend, prices, PRESETS[n], name=n) for n in names}


def constant_mix_index(prices: dict[str, pd.Series], weights: dict[str, float]) -> pd.Series:
    """Value of $1 in a mix rebalanced to fixed weights every trading day.

    Uses only days every ticker traded. Daily mix return = sum(w_i * r_i); the index starts at
    1.0 and compounds those returns. With one ticker this is just price / first price.
    Used for the fund-history view of risk, where there are no purchases to replay.
    """
    df = pd.concat({t: prices[t] for t in weights}, axis=1).dropna().sort_index()
    if len(df) < 2:
        raise ValueError("Need at least 2 common trading days.")
    rets = df.pct_change().iloc[1:]
    mix = sum(rets[t] * w for t, w in weights.items())
    growth = (1.0 + mix).cumprod()
    return pd.concat([pd.Series([1.0], index=df.index[:1]), growth]).rename("index")


def risk_table(series: dict[str, pd.Series], market: pd.Series, rf_annual: float) -> pd.DataFrame:
    """One row per price-like series: risk.risk_summary against the market, plus
    sml_gap = realized annual return minus the CAPM expected return (the dot's vertical
    distance from the SML). Series are clipped to the market's dates."""
    rows = []
    for name, s in series.items():
        s = s.dropna()
        s = s[s.index.isin(market.index)]
        m = market.loc[s.index]
        r = risk.risk_summary(s, m, rf_annual)
        rows.append({"name": name, **{k: r[k] for k in (
            "ann_return", "ann_vol", "sharpe", "max_drawdown", "beta", "alpha_annual",
            "r_squared", "capm_expected", "n", "ppy")}})
    df = pd.DataFrame(rows)
    df["sml_gap"] = df["ann_return"] - df["capm_expected"]
    return df


def market_annual_return(market: pd.Series, on: pd.DatetimeIndex) -> float:
    """Geometric annualized return of the market over the given dates (for the SML)."""
    m = market.loc[market.index.isin(on)]
    rets = risk.simple_returns(m)
    return risk.annualized_return(rets, risk.periods_per_year(m.index))
