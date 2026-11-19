"""Presentation helpers. OWNED BY THE DESIGNER (Grok).

Pages call these instead of styling things inline, so the designer can change how every card,
KPI row and chart looks without touching page logic. Builder rule: don't edit this file; if you
need a new helper, add a request to HANDOFF.md. Keep the function signatures stable.
"""

from __future__ import annotations

from contextlib import contextmanager

import altair as alt
import streamlit as st

import pandas as pd

from core.categorize import ALL_CATEGORIES
from core.portfolios import PRESETS

# Tokens from DESIGN.md (Ashton Capes site system). Pages may pass these into Altair color scales.
TEXT = "#17251E"
MUTED = "#42574B"
BORDER = "#CCD5CB"
GRID = "#E3E6DF"
SPENT = "#5B8FB9"  # cumulative spending: the baseline, in site blue (clearly apart from fairway)
SHADOW = "#17603A"  # fund value: the hero series, in fairway
CONTRIBUTIONS = "#5B8FB9"
GROWTH = "#17603A"
# 14 fills, one per ALL_CATEGORIES entry (13 rules + Other), from the site chart palette.
# Chart fills, not body text.
CATEGORICAL = [
    "#86958B",  # Transfers & Payments
    "#A3311F",  # Dining
    "#6B5208",  # Coffee
    "#8FBF7A",  # Groceries
    "#A8480A",  # Gas
    "#5B8FB9",  # Transport
    "#553A73",  # Subscriptions
    "#C9A227",  # Entertainment
    "#2F4A66",  # Travel
    "#17603A",  # Shopping
    "#4F8A8B",  # Health
    "#42574B",  # Housing & Utilities
    "#9B7BB5",  # Education
    "#A9B4AA",  # Other
]
CATEGORY_COLORS = dict(zip(ALL_CATEGORIES, CATEGORICAL))
ACCENT = "#17603A"
FAN_OUTER = "#CFE0D4"
FAN_INNER = "#8FBF7A"
HIST_FILL = "#6BA35F"  # solid bars, about 3:1 on white
# 3:1 non-text stroke on white/paper (the light fills alone are too faint).
BAND_STROKE = "#3E7A52"
PORTFOLIO_ORDER = list(PRESETS.keys()) + ["SPY (market)", "SPY"]
# Lines need 3:1 on white, so QQQ uses burnt orange, not the site gold.
PORTFOLIO_COLORS = {
    "100% VOO": "#17603A",
    "60/40 VOO/BND": "#5B8FB9",
    "100% BND": "#42574B",
    "100% QQQ": "#A8480A",
    "SPY (market)": "#17251E",
    "SPY": "#17251E",
}


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
                "labelFont": "Geist",
                "titleFont": "Geist",
                "labelFontSize": 12,
                "titleFontSize": 12,
            },
            "legend": {
                "orient": "bottom",
                "title": None,
                "labelColor": TEXT,
                "labelFont": "Geist",
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


def _field_values(c: alt.Chart, field: str) -> list[str]:
    data = getattr(c, "data", None)
    if data is None or not hasattr(data, "columns") or field not in getattr(data, "columns", []):
        return []
    return list(dict.fromkeys(str(v) for v in data[field].tolist()))


def _series_names(c: alt.Chart) -> list[str]:
    return _field_values(c, "series")


def _portfolio_scale(names: list[str]) -> alt.Scale:
    extras = [c for c in CATEGORICAL if c not in PORTFOLIO_COLORS.values()]
    domain: list[str] = []
    range_: list[str] = []
    extra_i = 0
    ordered = [n for n in PORTFOLIO_ORDER if n in names] + [n for n in names if n not in PORTFOLIO_ORDER]
    for name in ordered:
        domain.append(name)
        if name in PORTFOLIO_COLORS:
            range_.append(PORTFOLIO_COLORS[name])
        else:
            range_.append(extras[extra_i % len(extras)])
            extra_i += 1
    return alt.Scale(domain=domain, range=range_)


def _legend(columns: int) -> alt.Legend:
    """Legends wrap into fixed columns so they never run off a phone screen. Set on the encoding,
    because Streamlit's chart theme overrides legend settings given only in the config."""
    return alt.Legend(title=None, orient="bottom", columns=columns, columnPadding=14, rowPadding=6,
                      labelLimit=150, symbolSize=70, labelFontSize=12)


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
                legend=_legend(2),
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
                legend=_legend(2),
            )
        )
    if field == "category":
        seen = set(_field_values(c, "category"))
        domain = [k for k in CATEGORY_COLORS if k in seen] or list(CATEGORY_COLORS.keys())
        color_kwargs: dict = {
            "scale": alt.Scale(domain=domain, range=[CATEGORY_COLORS[k] for k in domain]),
        }
        if auto_category:
            color_kwargs["legend"] = None
        else:
            color_kwargs["legend"] = _legend(2)
        return c.encode(color=alt.Color("category:N", **color_kwargs))
    if field in {"name", "portfolio"}:
        names = _field_values(c, field) or list(PORTFOLIO_ORDER)
        return c.encode(
            color=alt.Color(
                f"{field}:N",
                title=None,
                scale=_portfolio_scale(names),
                legend=_legend(2),
            )
        )
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
        # Legends wrap into columns so they never run off a phone screen.
        .configure_legend(orient="bottom", title=None, labelColor=TEXT, labelFont="Geist", labelFontSize=12,
                          columns=2, columnPadding=14, rowPadding=6, labelLimit=150, symbolSize=70)
        .configure_view(strokeWidth=0, clip=False)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            gridColor=GRID,
            domainColor=BORDER,
            tickColor=BORDER,
            labelFont="Geist",
            titleFont="Geist",
            labelLimit=0,
            labelPadding=8,
            labelFlush=False,
        )
        .configure_range(category=CATEGORICAL)
        .configure_line(strokeWidth=2.5)
        .configure_area(opacity=0.9)
        .configure(background="transparent")
    )
    st.altair_chart(c, width="stretch", key=key)


def _frame_with_x(bands: pd.DataFrame, x: str) -> pd.DataFrame:
    df = bands if isinstance(bands, pd.DataFrame) else pd.DataFrame(bands)
    if x in df.columns:
        return df
    out = df.reset_index()
    if x not in out.columns and "index" in out.columns:
        out = out.rename(columns={"index": x})
    return out


def chart_fan(
    bands: pd.DataFrame,
    *,
    x: str = "age",
    y_title: str = "Balance ($)",
    key: str | None = None,
) -> None:
    """Percentile fan: p5-p95 tint, p25-p75 sage, p50 pine. Pass simulate_roth()['percentiles']."""
    df = _frame_with_x(bands, x)
    x_enc = alt.X(f"{x}:Q", title="Age")
    outer = (
        alt.Chart(df)
        .mark_area(opacity=0.9, color=FAN_OUTER, stroke=BAND_STROKE, strokeWidth=1)
        .encode(
            x=x_enc,
            y=alt.Y("p5:Q", title=y_title, axis=alt.Axis(format="$,.0f")),
            y2="p95:Q",
            tooltip=[
                alt.Tooltip(f"{x}:Q", title="Age"),
                alt.Tooltip("p5:Q", title="5th", format="$,.0f"),
                alt.Tooltip("p50:Q", title="Median", format="$,.0f"),
                alt.Tooltip("p95:Q", title="95th", format="$,.0f"),
            ],
        )
    )
    inner = (
        alt.Chart(df)
        .mark_area(opacity=0.9, color=FAN_INNER)
        .encode(x=x_enc, y="p25:Q", y2="p75:Q")
    )
    median = (
        alt.Chart(df)
        .mark_line(color=ACCENT, strokeWidth=2.5)
        .encode(x=x_enc, y="p50:Q")
    )
    chart(outer + inner + median, key=key)


def chart_histogram(
    values,
    *,
    markers: list[dict] | None = None,
    bins: int = 40,
    x_title: str = "Portfolio value ($)",
    key: str | None = None,
) -> None:
    """Histogram plus vertical rules. Each marker: label, value, optional color, optional dashed=True."""
    df = pd.DataFrame({"value": list(values)})
    layers: list[alt.Chart] = [
        alt.Chart(df)
        .mark_bar(color=HIST_FILL, binSpacing=1, cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X(
                "value:Q",
                bin=alt.Bin(maxbins=bins),
                title=x_title,
                axis=alt.Axis(format="$,.0f", labelOverlap=True),
            ),
            y=alt.Y("count()", title="Shuffles"),
        )
    ]
    for mark in markers or []:
        color = mark.get("color", ACCENT)
        rule_df = pd.DataFrame({"value": [mark["value"]], "label": [mark.get("label", "")]})
        rule_kw = dict(strokeWidth=2, color=color)
        if mark.get("dashed"):
            rule_kw["strokeDash"] = [6, 4]
        rule = alt.Chart(rule_df).mark_rule(**rule_kw).encode(
            x=alt.X("value:Q", title=x_title),
            tooltip=[
                alt.Tooltip("label:N", title="Mark"),
                alt.Tooltip("value:Q", title="Value", format="$,.2f"),
            ],
        )
        layers.append(rule)
    chart(alt.layer(*layers), key=key)


def chart_risk_return(df: pd.DataFrame, *, key: str | None = None) -> None:
    """Scatter: one portfolio per dot. Columns: name, ann_vol, ann_return."""
    names = list(dict.fromkeys(str(v) for v in df["name"].tolist()))
    c = (
        alt.Chart(df)
        .mark_circle(size=110, opacity=1, stroke='#ffffff', strokeWidth=1.5)
        .encode(
            x=alt.X("ann_vol:Q", title="Annualized volatility", axis=alt.Axis(format="%")),
            y=alt.Y("ann_return:Q", title="Annualized return", axis=alt.Axis(format="%")),
            color=alt.Color("name:N", title=None, scale=_portfolio_scale(names), legend=_legend(2)),
            tooltip=[
                alt.Tooltip("name:N", title="Portfolio"),
                alt.Tooltip("ann_vol:Q", title="Vol", format=".1%"),
                alt.Tooltip("ann_return:Q", title="Return", format=".1%"),
            ],
        )
    )
    chart(c, key=key)


def chart_sml(line_df: pd.DataFrame, points_df: pd.DataFrame, *, key: str | None = None) -> None:
    """Security market line plus portfolio dots. line: beta, expected_return. points: name, beta, ann_return."""
    names = list(dict.fromkeys(str(v) for v in points_df["name"].tolist()))
    line = (
        alt.Chart(line_df)
        .mark_line(color=ACCENT, strokeWidth=2)
        .encode(
            x=alt.X("beta:Q", title="Beta"),
            y=alt.Y("expected_return:Q", title="Annual return", axis=alt.Axis(format="%")),
        )
    )
    points = (
        alt.Chart(points_df)
        .mark_circle(size=110, opacity=1, stroke='#ffffff', strokeWidth=1.5)
        .encode(
            x=alt.X("beta:Q", title="Beta"),
            y=alt.Y("ann_return:Q", title="Annual return", axis=alt.Axis(format="%")),
            color=alt.Color("name:N", title=None, scale=_portfolio_scale(names), legend=_legend(2)),
            tooltip=[
                alt.Tooltip("name:N", title="Portfolio"),
                alt.Tooltip("beta:Q", title="Beta", format=".2f"),
                alt.Tooltip("ann_return:Q", title="Return", format=".1%"),
            ],
        )
    )
    chart((line + points).resolve_scale(y="shared"), key=key)
