"""Daily adjusted closes from Yahoo Finance.

Only the ticker and a date range leave the machine. No transaction data is sent anywhere.
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

TICKER_RE = re.compile(r"^[A-Z0-9.\-^]{1,10}$")


def clean_ticker(raw: str) -> str | None:
    t = raw.strip().upper()
    return t if TICKER_RE.match(t) else None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_adjusted_close(ticker: str, start: pd.Timestamp) -> pd.Series:
    """Adjusted close (dividends and splits folded in) from `start` through today, so the
    portfolio is marked to the latest close. Raises RuntimeError on failure."""
    import yfinance as yf

    try:
        hist = yf.Ticker(ticker).history(
            start=start.strftime("%Y-%m-%d"),
            end=(pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=True,
        )
    except Exception as exc:  # network errors, Yahoo outages
        raise RuntimeError(f"Could not download prices for {ticker}: {exc}") from exc
    if hist is None or hist.empty or "Close" not in hist:
        raise RuntimeError(f"No price data for {ticker}. Check the ticker symbol.")
    close = hist["Close"].dropna()
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    close = close[~close.index.duplicated(keep="last")]
    return close.astype(float)


MARKET_PROXY = "SPY"  # total-return S&P 500 ETF, the "market" for beta and CAPM
RISK_FREE_TICKER = "^IRX"  # 13-week US T-bill, quoted as a discount yield in percent


def fetch_many(tickers: list[str], start: pd.Timestamp) -> dict[str, pd.Series]:
    """Adjusted closes for several tickers (each call is cached). Raises RuntimeError if any fails."""
    return {t: fetch_adjusted_close(t, start) for t in tickers}


def fetch_history(ticker: str, years: int = 10) -> pd.Series:
    """Long daily history for Monte Carlo bootstrapping and fund-level risk stats."""
    start = (pd.Timestamp.today().normalize() - pd.DateOffset(years=years))
    return fetch_adjusted_close(ticker, start)


def tbill_effective_annual(discount_yield: float, days: int = 91) -> float:
    """Convert a T-bill bank discount yield (decimal, e.g. 0.0414) to an effective annual rate.

    Bank discount basis: price = 1 - d * days / 360. Holding-period return = 1 / price - 1.
    Effective annual rate = (1 + HPR) ^ (365 / days) - 1. Example: d = 4.143% gives
    price 0.989527, HPR 1.0584%, EAR 4.31%.
    """
    price = 1 - discount_yield * days / 360
    hpr = 1 / price - 1
    return (1 + hpr) ** (365 / days) - 1


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_risk_free() -> dict:
    """Latest 13-week T-bill yield from Yahoo (^IRX), as an effective annual rate.
    Returns {'discount_yield', 'effective_annual', 'as_of'}. Raises RuntimeError on failure."""
    start = pd.Timestamp.today().normalize() - pd.Timedelta(days=14)
    quotes = fetch_adjusted_close(RISK_FREE_TICKER, start)
    d = float(quotes.iloc[-1]) / 100
    return {"discount_yield": d, "effective_annual": tbill_effective_annual(d), "as_of": quotes.index[-1]}
