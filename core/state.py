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
SAMPLE_FLAG = "is_builtin_sample"
WANTS_MAP_KEY = "custom_wants"  # {custom category: is a want}, see core/edits.py


def get_transactions() -> pd.DataFrame | None:
    return st.session_state.get(TX_KEY)


def set_transactions(df: pd.DataFrame, source_name: str, is_sample: bool | None = None) -> None:
    """is_sample: True only for the built-in sample button; None keeps the current flag (edits)."""
    if st.session_state.get(SOURCE_KEY) != source_name or is_sample is not None:
        st.session_state.pop("invest_dollars", None)  # new data: refill the suggested monthly amount
        st.session_state.pop(WANTS_MAP_KEY, None)  # and forget the old file's custom categories
    st.session_state[TX_KEY] = df
    st.session_state[SOURCE_KEY] = source_name
    if is_sample is not None:
        st.session_state[SAMPLE_FLAG] = is_sample


def clear_transactions() -> None:
    # invest_mode / invest_dollars: the shared choice from core/invest.py, refilled for the new data
    for k in (TX_KEY, SOURCE_KEY, SAMPLE_FLAG, "invest_mode", "invest_dollars", WANTS_MAP_KEY):
        st.session_state.pop(k, None)


def spending_only(df: pd.DataFrame, include_transfers: bool = False) -> pd.DataFrame:
    from core.categorize import NON_SPEND

    if "ignored" in df.columns:  # rows the user marked "Ignore" are left out of every total
        df = df[~df["ignored"].astype(bool)]
    return df if include_transfers else df[~df["category"].isin(NON_SPEND)]


def wants_map() -> dict[str, bool]:
    return dict(st.session_state.get(WANTS_MAP_KEY, {}))


def set_wants_map(m: dict[str, bool]) -> None:
    st.session_state[WANTS_MAP_KEY] = dict(m)


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
