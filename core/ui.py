"""Presentation helpers. OWNED BY THE DESIGNER (Grok).

Pages call these instead of styling things inline, so the designer can change how every card,
KPI row and chart looks without touching page logic. Builder rule: don't edit this file; if you
need a new helper, add a request to HANDOFF.md. Keep the function signatures stable.
"""

from __future__ import annotations

from contextlib import contextmanager

import altair as alt
import streamlit as st


@contextmanager
def section(key: str, title: str | None = None, border: bool = True):
    """A card. CSS hook: .st-key-<key>"""
    with st.container(key=key, border=border):
        if title:
            st.subheader(title)
        yield


def kpi_row(key: str, items: list[dict]) -> None:
    """items: dicts of st.metric kwargs (label, value, and optional delta, help)."""
    with st.container(key=key):
        for col, item in zip(st.columns(len(items)), items):
            col.metric(**item)


def chart(c: alt.Chart, key: str | None = None) -> None:
    """Every chart goes through here so axis, legend and font styling live in one place."""
    c = c.configure_legend(orient="bottom", title=None).configure_view(strokeWidth=0)
    st.altair_chart(c, width="stretch", key=key)
