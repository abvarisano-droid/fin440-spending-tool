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

# Tokens from DESIGN.md v4 (Ashton Capes site, Liquid Glass v8 light). Pages may pass these into Altair color scales.
TEXT = "#1A1D1B"
MUTED = "#4F5752"
BORDER = "#DCDFD8"
GRID = "#E3E9E8"  # y gridlines only; quiet on the glass card
FONT = "Geist"
SPENT = "#B0603A"  # cumulative spending: the baseline, in site chart copper (clearly apart from teal)
SHADOW = "#0A716C"  # fund value: the hero series, in site teal
CONTRIBUTIONS = "#3F6F9E"
GROWTH = "#0A716C"
# 14 fills, one per ALL_CATEGORIES entry (13 rules + Other), from the site chart palette.
# Chart fills, not body text.
CATEGORICAL = [
    "#8F958F",  # Transfers & Payments
    "#A3311F",  # Dining
    "#6B5208",  # Coffee
    "#4F7A3A",  # Groceries
    "#B0603A",  # Gas
    "#3F6F9E",  # Transport
    "#553A73",  # Subscriptions
    "#C9A227",  # Entertainment
    "#2F4A66",  # Travel
    "#0A716C",  # Shopping
    "#B04C82",  # Health (rose: apart from the Shopping teal)
    "#4F5752",  # Housing & Utilities
    "#9B7BB5",  # Education
    "#B4BAB5",  # Other
]
CATEGORY_COLORS = dict(zip(ALL_CATEGORIES, CATEGORICAL))
ACCENT = "#0A716C"
FAN_OUTER = "#C4F6F3"
FAN_INNER = "#6FD9D1"
HIST_FILL = "#2FA59E"  # solid bars, about 3:1 on white
# 3:1 non-text stroke on white/paper (the light fills alone are too faint).
BAND_STROKE = "#0A716C"
PORTFOLIO_ORDER = list(PRESETS.keys()) + ["SPY (market)", "SPY"]
# Lines need 3:1 on white. SCHD is plum (7.16:1 on white, 6.57:1 on paper), apart from teal, blue and grey.
PORTFOLIO_COLORS = {
    "100% VOO": "#0A716C",
    "60/40 VOO/BND": "#3F6F9E",
    "100% BND": "#4F5752",
    "100% SCHD": "#7B3F8C",
    "SPY (market)": "#1A1D1B",
    "SPY": "#1A1D1B",
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
                "domain": False,
                "ticks": False,
                "labelFont": FONT,
                "titleFont": FONT,
                "labelFontSize": 12,
                "titleFontSize": 12,
                "titleFontWeight": 500,
            },
            "axisX": {"grid": False},
            "legend": {
                "orient": "top",
                "title": None,
                "labelColor": TEXT,
                "labelFont": FONT,
                "labelFontSize": 12.5,
                "symbolType": "circle",
            },
            "range": {"category": CATEGORICAL},
            "bar": {"stroke": None},
            "line": {"strokeWidth": 2.25, "strokeCap": "round", "strokeJoin": "round"},
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


def _mark_type(c) -> str | None:
    mark = getattr(c, "mark", alt.Undefined)
    if isinstance(mark, str):
        return mark
    t = getattr(mark, "type", alt.Undefined)
    return t if isinstance(t, str) else None


def _restyle_mark(c: alt.Chart, **props) -> alt.Chart:
    """Add mark properties while keeping the ones the page set (e.g. interpolate)."""
    mark = getattr(c, "mark", alt.Undefined)
    if isinstance(mark, str):
        spec = {"type": mark}
    elif hasattr(mark, "to_dict"):
        spec = mark.to_dict()
    else:
        return c
    for k, v in props.items():
        spec.setdefault(k, v)
    out = c.copy(deep=False)
    out.mark = alt.MarkDef(**spec)
    return out


_CURRENT_MARK: list[str | None] = [None]


def _legend(columns: int) -> alt.Legend:
    """Legends sit above the plot, top left, and wrap into fixed columns so they never run off a
    phone screen. Set on the encoding, because Streamlit's chart theme overrides legend settings
    given only in the config. Line charts get a short stroke as the key, other marks a dot."""
    is_line = _CURRENT_MARK[0] == "line"
    return alt.Legend(
        title=None, orient="top", direction="horizontal", columns=columns, columnPadding=20,
        rowPadding=8, labelLimit=170, labelFontSize=12.5, labelColor=TEXT, labelFont=FONT,
        symbolType="stroke" if is_line else "circle", symbolSize=180 if is_line else 90,
        symbolStrokeWidth=3 if is_line else 0, offset=14, padding=0,
    )


def _apply_named_series_colors(c: alt.Chart) -> alt.Chart:
    """Map shadow/roth/category series to DESIGN.md colors."""
    _CURRENT_MARK[0] = _mark_type(c)
    field = _color_field(c)
    if field is None and (
        _channel_field(c, "y") == "category" or _channel_field(c, "x") == "category"
    ):
        # A ranked bar list whose axis already names each category: one teal fill, rounded
        # bar ends, no legend. Color adds nothing the axis does not already say.
        if _mark_type(c) == "bar":
            horizontal = _channel_field(c, "y") == "category"
            band = "y" if horizontal else "x"
            enc = _channel_encoding(c, band).copy(deep=True)
            enc.scale = alt.Scale(paddingInner=0.32, paddingOuter=0.1)
            return _restyle_mark(c, color=ACCENT, cornerRadiusEnd=5).encode(**{band: enc})
        return c
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
        out = c.encode(color=alt.Color(
            "category:N",
            scale=alt.Scale(domain=domain, range=[CATEGORY_COLORS[k] for k in domain]),
            legend=_legend(2),
        ))
        if _mark_type(c) == "bar":
            # Stacked bars: a hairline of paper between segments so neighbors read apart.
            out = _restyle_mark(out, stroke="#FFFFFF", strokeWidth=1)
            x = _channel_encoding(out, "x")
            if x is not None and _channel_field(out, "x") not in (None, "category"):
                xe = x.copy(deep=True)
                if getattr(xe, "scale", alt.Undefined) is alt.Undefined:
                    xe.scale = alt.Scale(paddingInner=0.38)
                    try:
                        out = out.encode(x=xe)
                    except Exception:
                        pass
        return out
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


def _tight_age_axis(c: alt.Chart) -> alt.Chart:
    """An age axis starts at the first age in the data (no zero, no nice rounding down to 20)."""
    if not isinstance(c, alt.Chart) or _channel_field(c, "x") != "age":
        return c
    x = _channel_encoding(c, "x").copy(deep=True)
    x.scale = alt.Scale(zero=False, nice=False)
    return c.encode(x=x)


def _delta_is_loss(delta: object) -> bool:
    return str(delta).lstrip().startswith("-")


@contextmanager
def section(key: str, title: str | None = None, border: bool = True):
    """A card. CSS hook: .st-key-<key>"""
    with st.container(key=key, border=border):
        if title:
            st.subheader(title)
        yield


def page_header(title: str, *, course: str | None = None, lede: str | None = None) -> None:
    """Page intro: serif title, the FIN 440 course chip, then one lede line.

    `course` is the chapter text without the icon (the school icon is added here); `lede` is the
    plain caption that explains the page. CSS hook: .st-key-page_head."""
    with st.container(key="page_head"):
        st.title(title)
        if course:
            st.caption(f":material/school: {course}")
        if lede:
            st.caption(lede)


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
    c = _tight_age_axis(c)
    c = (
        c.properties(padding={"left": 4, "right": 8, "top": 4, "bottom": 4})
        # Legends sit above the plot and wrap into columns so they never run off a phone screen.
        .configure_legend(orient="top", title=None, labelColor=TEXT, labelFont=FONT, labelFontSize=12.5,
                          columns=2, columnPadding=20, rowPadding=8, labelLimit=170)
        .configure_view(strokeWidth=0, clip=False)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            gridColor=GRID,
            domain=False,
            ticks=False,
            labelFont=FONT,
            titleFont=FONT,
            labelFontSize=12,
            titleFontSize=12,
            titleFontWeight=500,
            titlePadding=12,
            labelLimit=0,
            labelPadding=8,
            labelFlush=False,
        )
        .configure_axisX(grid=False, domain=True, domainColor=BORDER)
        .configure_range(category=CATEGORICAL)
        .configure_line(strokeWidth=2.25, strokeCap="round", strokeJoin="round")
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
    """Percentile fan: p5-p95 pale cyan, p25-p75 mid cyan, p50 teal. Pass simulate_roth()['percentiles']."""
    df = _frame_with_x(bands, x)
    x_enc = alt.X(f"{x}:Q", title="Age", scale=alt.Scale(zero=False, nice=False))
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


MARKET_NAMES = ("SPY (market)", "SPY")


def _is_market(name: object) -> bool:
    return str(name) in MARKET_NAMES


def _dots_with_market_ring(df: pd.DataFrame, x: alt.X, y: alt.Y, tooltip: list) -> alt.LayerChart:
    """Portfolios as filled dots; the market (SPY) as a hollow ring drawn on top, so a portfolio
    that sits on the market (VOO, beta 0.99) still shows through inside the ring."""
    names = list(dict.fromkeys(str(v) for v in df["name"].tolist()))
    color = alt.Color("name:N", title=None, scale=_portfolio_scale(names), legend=_legend(2))
    is_mkt = df["name"].map(_is_market)
    dots = (
        alt.Chart(df[~is_mkt])
        .mark_circle(size=110, opacity=1, stroke="#ffffff", strokeWidth=1.5)
        .encode(x=x, y=y, color=color, tooltip=tooltip)
    )
    ring = (
        alt.Chart(df[is_mkt])
        .mark_point(shape="circle", filled=False, size=300, strokeWidth=2.5, opacity=1)
        .encode(x=x, y=y, color=color, tooltip=tooltip)
    )
    return alt.layer(dots, ring)


def chart_risk_return(df: pd.DataFrame, *, key: str | None = None) -> None:
    """Scatter: one portfolio per dot, the market as a ring. Columns: name, ann_vol, ann_return."""
    c = _dots_with_market_ring(
        df,
        alt.X("ann_vol:Q", title="Annualized volatility", axis=alt.Axis(format="%")),
        alt.Y("ann_return:Q", title="Annualized return", axis=alt.Axis(format="%")),
        [
            alt.Tooltip("name:N", title="Portfolio"),
            alt.Tooltip("ann_vol:Q", title="Vol", format=".1%"),
            alt.Tooltip("ann_return:Q", title="Return", format=".1%"),
        ],
    )
    chart(c, key=key)


def chart_sml(line_df: pd.DataFrame, points_df: pd.DataFrame, *, key: str | None = None) -> None:
    """Security market line plus portfolio dots (market as a ring). line: beta, expected_return.
    points: name, beta, ann_return."""
    line = (
        alt.Chart(line_df)
        .mark_line(color=ACCENT, strokeWidth=2)
        .encode(
            x=alt.X("beta:Q", title="Beta"),
            y=alt.Y("expected_return:Q", title="Annual return", axis=alt.Axis(format="%")),
        )
    )
    points = _dots_with_market_ring(
        points_df,
        alt.X("beta:Q", title="Beta"),
        alt.Y("ann_return:Q", title="Annual return", axis=alt.Axis(format="%")),
        [
            alt.Tooltip("name:N", title="Portfolio"),
            alt.Tooltip("beta:Q", title="Beta", format=".2f"),
            alt.Tooltip("ann_return:Q", title="Return", format=".1%"),
        ],
    )
    chart(alt.layer(line, points).resolve_scale(y="shared"), key=key)
