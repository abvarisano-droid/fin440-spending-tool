"""Presentation helpers. OWNED BY THE DESIGNER (Grok).

Pages call these instead of styling things inline, so the designer can change how every card,
KPI row and chart looks without touching page logic. Builder rule: don't edit this file; if you
need a new helper, add a request to HANDOFF.md. Keep the function signatures stable.
"""

from __future__ import annotations

from contextlib import contextmanager

import altair as alt
import streamlit as st

# Tokens from DESIGN.md. Pages may pass these into Altair color scales.
TEXT = "#1C1915"
MUTED = "#6E675C"
BORDER = "#DDD4C6"
GRID = "#E6DDD0"
SPENT = "#2C4A6E"
SHADOW = "#B45309"
CONTRIBUTIONS = "#2C4A6E"
GROWTH = "#1E6B45"
CATEGORICAL = [
    "#1E4A3A",
    "#A33B32",
    "#2C4A6E",
    "#B45309",
    "#5C6B4A",
    "#6B3D4A",
    "#6E675C",
    "#3D5A4C",
]


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


def _encoding_color(c: alt.Chart):
    encoding = getattr(c, "encoding", None)
    if encoding is None:
        return None
    color = getattr(encoding, "color", alt.Undefined)
    if color is alt.Undefined or color is None:
        return None
    return color


def _color_field(c: alt.Chart) -> str | None:
    color = _encoding_color(c)
    if color is None or not hasattr(color, "to_dict"):
        return None
    try:
        spec = color.to_dict()
    except Exception:
        return None
    if not isinstance(spec, dict):
        return None
    field = spec.get("field")
    return str(field) if field else None


def _apply_named_series_colors(c: alt.Chart) -> alt.Chart:
    """Map shadow/roth series to DESIGN.md colors when the page left the scale default."""
    field = _color_field(c)
    if field == "series":
        return c.encode(
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(range=[SPENT, SHADOW]),
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
    return c


def _delta_is_loss(delta: object) -> bool:
    text = str(delta).lstrip()
    return text.startswith("$-") or text.startswith("-")


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
        c.configure_legend(orient="bottom", title=None, labelColor=TEXT, labelFont="Source Sans 3")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            gridColor=GRID,
            domainColor=BORDER,
            tickColor=BORDER,
            labelFont="Source Sans 3",
            titleFont="Source Sans 3",
        )
        .configure_range(category=CATEGORICAL)
        .configure_line(strokeWidth=2.5)
        .configure_area(opacity=0.9)
        .configure_bar(stroke=None)
    )
    st.altair_chart(c, width="stretch", key=key)
