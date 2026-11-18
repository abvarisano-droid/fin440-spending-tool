"""Presentation helpers. OWNED BY THE DESIGNER (Grok).

Pages call these instead of styling things inline, so the designer can change how every card,
KPI row and chart looks without touching page logic. Builder rule: don't edit this file; if you
need a new helper, add a request to HANDOFF.md. Keep the function signatures stable.
"""

from __future__ import annotations

from contextlib import contextmanager

import altair as alt
import streamlit as st

from core.categorize import ALL_CATEGORIES

# Tokens from DESIGN.md. Pages may pass these into Altair color scales.
TEXT = "#1C1915"
MUTED = "#6E675C"
BORDER = "#DDD4C6"
GRID = "#E6DDD0"
SPENT = "#2C4A6E"
SHADOW = "#B45309"
CONTRIBUTIONS = "#2C4A6E"
GROWTH = "#1E6B45"
# 14 fills, one per ALL_CATEGORIES entry (13 rules + Other). Chart fills, not body text.
CATEGORICAL = [
    "#6E675C",  # Transfers & Payments
    "#A33B32",  # Dining
    "#6B5428",  # Coffee
    "#5C6B4A",  # Groceries
    "#8A5A4A",  # Gas
    "#4A5A6B",  # Transport
    "#2C4A6E",  # Subscriptions
    "#6B3D4A",  # Entertainment
    "#3A4F3A",  # Travel
    "#B45309",  # Shopping
    "#3D5A4C",  # Health
    "#1E4A3A",  # Housing & Utilities
    "#4A3A5A",  # Education
    "#5A6B5A",  # Other
]
CATEGORY_COLORS = dict(zip(ALL_CATEGORIES, CATEGORICAL))


@alt.theme.register("spend_shadow", enable=True)
def _spend_shadow_theme() -> alt.theme.ThemeConfig:
    return {
        "config": {
            "view": {"strokeWidth": 0, "stroke": None},
            "axis": {
                "labelColor": MUTED,
                "titleColor": MUTED,
                "gridColor": GRID,
                "domainColor": BORDER,
                "tickColor": BORDER,
                "labelFont": "Source Sans 3",
                "titleFont": "Source Sans 3",
                "labelFontSize": 12,
                "titleFontSize": 12,
            },
            "legend": {
                "orient": "bottom",
                "title": None,
                "labelColor": TEXT,
                "labelFont": "Source Sans 3",
                "labelFontSize": 12,
                "symbolType": "circle",
            },
            "range": {"category": CATEGORICAL},
            "bar": {"stroke": None},
            "line": {"strokeWidth": 2.5},
            "area": {"stroke": None, "opacity": 0.9},
        }
    }


def _channel_encoding(c: alt.Chart, channel: str):
    encoding = getattr(c, "encoding", None)
    if encoding is None:
        return None
    enc = getattr(encoding, channel, alt.Undefined)
    if enc is alt.Undefined or enc is None:
        return None
    return enc


def _channel_field(c: alt.Chart, channel: str) -> str | None:
    enc = _channel_encoding(c, channel)
    if enc is None or not hasattr(enc, "to_dict"):
        return None
    try:
        spec = enc.to_dict()
    except Exception:
        return None
    if not isinstance(spec, dict):
        return None
    field = spec.get("field")
    return str(field) if field else None


def _color_field(c: alt.Chart) -> str | None:
    return _channel_field(c, "color")


def _series_names(c: alt.Chart) -> list[str]:
    data = getattr(c, "data", None)
    if data is None or not hasattr(data, "columns") or "series" not in getattr(data, "columns", []):
        return []
    return list(dict.fromkeys(str(v) for v in data["series"].tolist()))


def _apply_named_series_colors(c: alt.Chart) -> alt.Chart:
    """Map shadow/roth/category series to DESIGN.md colors."""
    field = _color_field(c)
    auto_category = False
    if field is None and (
        _channel_field(c, "y") == "category" or _channel_field(c, "x") == "category"
    ):
        auto_category = True
        field = "category"
    if field == "series":
        names = _series_names(c)
        spent = next((n for n in names if n.startswith("Spent")), "Spent (cumulative)")
        other = next((n for n in names if n != spent), "Value")
        return c.encode(
            color=alt.Color(
                "series:N",
                title=None,
                sort=[spent, other],
                scale=alt.Scale(domain=[spent, other], range=[SPENT, SHADOW]),
            )
        )
    if field == "part":
        return c.encode(
            color=alt.Color(
                "part:N",
                title=None,
                sort=["Contributions", "Growth"],
                scale=alt.Scale(
                    domain=["Contributions", "Growth"],
                    range=[CONTRIBUTIONS, GROWTH],
                ),
            )
        )
    if field == "category":
        domain = list(CATEGORY_COLORS.keys())
        color_kwargs: dict = {
            "scale": alt.Scale(domain=domain, range=[CATEGORY_COLORS[k] for k in domain]),
        }
        if auto_category:
            color_kwargs["legend"] = None
        else:
            color_kwargs["title"] = "Category"
        return c.encode(color=alt.Color("category:N", **color_kwargs))
    return c


def _delta_is_loss(delta: object) -> bool:
    return str(delta).lstrip().startswith("-")


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
        cols = st.columns(len(items), gap="small", wrap=True)
        for i, (col, item) in enumerate(zip(cols, items)):
            kwargs = dict(item)
            kwargs.setdefault("border", True)
            if key == "shadow_kpis" and i == 1:
                sig = "shadow_signature_down" if _delta_is_loss(kwargs.get("delta")) else "shadow_signature"
                with col, st.container(key=sig):
                    st.metric(**kwargs)
            else:
                col.metric(**kwargs)


def chart(c: alt.Chart, key: str | None = None) -> None:
    """Every chart goes through here so axis, legend and font styling live in one place."""
    c = _apply_named_series_colors(c)
    c = (
        c.properties(padding={"left": 12, "right": 8, "top": 8, "bottom": 8})
        .configure_legend(orient="bottom", title=None, labelColor=TEXT, labelFont="Source Sans 3")
        .configure_view(strokeWidth=0, clip=False)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            gridColor=GRID,
            domainColor=BORDER,
            tickColor=BORDER,
            labelFont="Source Sans 3",
            titleFont="Source Sans 3",
            labelLimit=0,
            labelPadding=8,
            labelFlush=False,
        )
        .configure_range(category=CATEGORICAL)
        .configure_line(strokeWidth=2.5)
        .configure_area(opacity=0.9)
        .configure_bar(stroke=None)
    )
    st.altair_chart(c, width="stretch", key=key)
