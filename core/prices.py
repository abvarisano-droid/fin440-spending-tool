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
