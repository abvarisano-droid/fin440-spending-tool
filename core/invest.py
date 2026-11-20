"""How much goes in: a percent of wants, or an exact dollar amount every month.

The choice is shared by the Shadow and Roth pages, so picking "Exact $ per month" on one page
runs the other page's math off the same dollars.

- Percent of wants (the default): the Shadow invests that share of every want purchase, on its
  own date (100% = every want, the original what-if). The Roth contributes that share of the
  average monthly wants, rounded to the nearest $25 (see core/suggest.py).
- Exact $ per month: the Shadow buys that amount on the 1st of every calendar month from the
  first to the last month of spending (dollar-cost averaging); the Roth contributes it monthly.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

PERCENT = "Percent of wants"
DOLLARS = "Exact $ per month"
MODES = [PERCENT, DOLLARS]
MODE_KEY = "invest_mode"  # shared, not a widget key (Streamlit drops widget state between pages)
DOLLARS_KEY = "invest_dollars"


def scale_purchases(spend: pd.DataFrame, share: float) -> pd.DataFrame:
    """Each purchase invests `share` (0 to 1) of its amount, on its own date."""
    if not 0 < share <= 1:
        raise ValueError("Share must be above 0% and at most 100%.")
    return spend.assign(amount=spend["amount"] * share)


def monthly_buys(spend: pd.DataFrame, dollars: float) -> pd.DataFrame:
    """One buy of `dollars` on the 1st of each calendar month the spending spans."""
    if dollars <= 0:
        raise ValueError("Enter an amount above $0.")
    if spend.empty:
        return pd.DataFrame(columns=["date", "description", "amount"])
    months = pd.period_range(spend["date"].min().to_period("M"), spend["date"].max().to_period("M"), freq="M")
    return pd.DataFrame({"date": months.to_timestamp(), "description": "Monthly investment",
                         "amount": float(dollars)})


# Streamlit glue: one shared value, a widget per page that reads and writes it -----------------

def _write_back(widget_key: str, shared_key: str) -> None:
    st.session_state[shared_key] = st.session_state[widget_key]


def mode_radio(where, page: str, help: str | None = None) -> str:
    """The percent / dollars switch. `where` is st or a column; `page` makes the widget key unique."""
    wkey = f"{page}_invest_mode"
    st.session_state.setdefault(MODE_KEY, PERCENT)
    st.session_state[wkey] = st.session_state[MODE_KEY]
    return where.radio("How much goes in", MODES, horizontal=True, key=wkey, help=help,
                       on_change=_write_back, args=(wkey, MODE_KEY))


def dollars_input(where, page: str, default: float) -> float:
    """The shared monthly dollar amount, first filled with `default`."""
    wkey = f"{page}_invest_dollars"
    st.session_state.setdefault(DOLLARS_KEY, float(default))
    st.session_state[wkey] = st.session_state[DOLLARS_KEY]
    return where.number_input("Per month ($)", 1.0, 10_000.0, step=25.0, format="%.0f", key=wkey,
                              help="The same amount every month. It carries over between the Shadow "
                                   "and Roth pages.",
                              on_change=_write_back, args=(wkey, DOLLARS_KEY))


def clear() -> None:
    for k in (MODE_KEY, DOLLARS_KEY):
        st.session_state.pop(k, None)
