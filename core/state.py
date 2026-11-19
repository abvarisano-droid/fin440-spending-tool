"""Session-only storage. Uploaded data lives in st.session_state and is never written to disk."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = ROOT / "sample_data" / "sample_transactions.csv"
STYLES_CSS = ROOT / "styles.css"

TX_KEY = "transactions"  # normalized + categorized DataFrame
SOURCE_KEY = "source_name"


def get_transactions() -> pd.DataFrame | None:
    return st.session_state.get(TX_KEY)


def set_transactions(df: pd.DataFrame, source_name: str) -> None:
    st.session_state[TX_KEY] = df
    st.session_state[SOURCE_KEY] = source_name


def clear_transactions() -> None:
    for k in (TX_KEY, SOURCE_KEY):
        st.session_state.pop(k, None)


def spending_only(df: pd.DataFrame, include_transfers: bool = False) -> pd.DataFrame:
    from core.categorize import NON_SPEND

    return df if include_transfers else df[~df["category"].isin(NON_SPEND)]


def discretionary_monthly(spend: pd.DataFrame) -> float:
    """Average discretionary ("wants") spending per calendar month that has any spending."""
    if spend.empty:
        return 0.0
    months = max(spend["date"].dt.to_period("M").nunique(), 1)
    return float(spend.loc[spend["discretionary"], "amount"].sum() / months)


def require_transactions() -> pd.DataFrame:
    """Stop the page with a pointer to Upload if nothing is loaded yet."""
    df = get_transactions()
    if df is None or df.empty:
        st.info("No transactions loaded yet. Upload a CSV or load the sample data first.")
        st.page_link("app_pages/upload.py", label="Go to Upload", icon=":material/upload:")
        st.stop()
    return df


def load_styles() -> None:
    """Inject styles.css if the design files have landed. No-op until then."""
    if STYLES_CSS.exists():
        st.html(f"<style>{STYLES_CSS.read_text(encoding='utf-8')}</style>")
