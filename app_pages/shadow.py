import altair as alt
import pandas as pd
import streamlit as st

from core import lab, ui
from core.categorize import ALL_CATEGORIES
from core.portfolios import PRESETS
from core.prices import clean_ticker, fetch_adjusted_close, fetch_many
from core.shadow import build_shadow
from core.state import require_transactions, spending_only

st.title("Shadow portfolio")
st.caption(":material/school: FIN 440 link (Bodie, Kane & Marcus, 13e): Ch 2 (asset classes, stock and bond indexes), Ch 5 (holding-period returns, compounding), Ch 7 (stock-bond diversification).")
st.caption(
    "What if every purchase had bought an index fund instead? Each dollar buys fractional "
    "shares at the close of the first trading day on or after the purchase. Prices are "
    "dividend-adjusted, so dividends count as reinvested. No fees or taxes. Only the ticker and "
    "your earliest purchase date go to Yahoo Finance."
)
tx = spending_only(require_transactions())

with ui.section("shadow_controls"):
    c1, c2 = st.columns([1, 2])
    raw_ticker = c1.text_input("Fund ticker", value="VOO", max_chars=10, key="shadow_ticker",
                               help="Any Yahoo Finance ticker, e.g. VOO, VTI, QQQ, SCHD.")
    present = [c for c in ALL_CATEGORIES if c in set(tx["category"])]
    cats = c2.multiselect("Categories to shadow", present, default=present, key="shadow_cats")

ticker = clean_ticker(raw_ticker)
if ticker is None:
    st.error("That doesn't look like a ticker. Use letters, numbers, dots or dashes.")
    st.stop()
spend = tx[tx["category"].isin(cats)]
if spend.empty:
    st.warning("Pick at least one category.")
    st.stop()

with st.spinner(f"Getting {ticker} prices..."):
    try:
        prices = fetch_adjusted_close(ticker, spend["date"].min())
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

res = build_shadow(spend, prices)

ui.kpi_row("shadow_kpis", [
    dict(label="You spent", value=f"${res.invested:,.2f}"),
    dict(label=f"In {ticker} it'd be worth", value=f"${res.value:,.2f}",
         # sign first: Streamlit only colors a delta red/down when it starts with "-"
         delta=f"{'-' if round(res.gain, 2) < 0 else '+'}${abs(res.gain):,.2f} "
               f"({res.simple_return:+.2%})"),
    dict(label="Annualized (XIRR)", value=f"{res.xirr:+.2%}" if res.xirr is not None else "n/a",
         help="Money-weighted annual return, accounting for when each dollar went in. "
              "Shown as n/a for spans under a week. Annualizing a short span exaggerates it."),
    dict(label="Priced as of", value=f"{res.as_of:%b %d, %Y}",
         help="Latest Yahoo Finance price. During market hours today's price is intraday, "
              "not a close. Prices refresh hourly."),
])

if res.skipped:
    st.info(f"{res.skipped} purchase(s) are after the latest {ticker} close and are left out.")

timeline = res.timeline.melt("date", ["invested", "value"], var_name="series", value_name="dollars")
timeline["series"] = timeline["series"].map({"invested": "Spent (cumulative)", "value": f"Value in {ticker}"})
with ui.section("chart_shadow", "Spent vs. shadow value"):
    ui.chart(
        alt.Chart(timeline)
        .mark_line(interpolate="step-after")
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("dollars:Q", title="Dollars"),
            color=alt.Color("series:N", title=None),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("series:N", title="Series"),
                     alt.Tooltip("dollars:Q", title="Dollars", format="$,.2f")],
        ),
    )

with ui.section("shadow_compare", "Same purchases, four portfolios"):
    st.caption("Each purchase is split across funds by fixed weights and held, no rebalancing. "
               "Diversification in practice: compare how far each line swings, not only where it ends.")
    picks = st.multiselect("Portfolios", list(PRESETS), default=list(PRESETS), max_selections=4,
                           key="compare_pick")
    if picks:
        try:
            with st.spinner("Getting fund prices..."):
                cmp_prices = fetch_many(lab.tickers_for(picks), spend["date"].min())
            ports = lab.preset_portfolios(spend, cmp_prices, picks)
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
        else:
            lines = pd.concat([p.timeline.assign(name=n) for n, p in ports.items()])
            ui.chart(
                alt.Chart(lines)
                .mark_line(interpolate="step-after")
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("value:Q", title="Value ($)"),
                    color=alt.Color("name:N", title=None),
                    tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("name:N", title="Portfolio"),
                             alt.Tooltip("value:Q", title="Value", format="$,.2f")],
                ),
                key="compare_chart",
            )
            st.dataframe(
                pd.DataFrame([{
                    "Portfolio": n, "Worth now": p.value, "Gain": p.gain, "Spent": p.invested,
                    "Return": p.simple_return * 100,
                    "XIRR": p.xirr * 100 if p.xirr is not None else None,
                } for n, p in ports.items()]),
                hide_index=True,
                column_config={
                    "Portfolio": st.column_config.TextColumn("Portfolio", pinned=True),
                    "Spent": st.column_config.NumberColumn(format="dollar"),
                    "Worth now": st.column_config.NumberColumn(format="dollar"),
                    "Gain": st.column_config.NumberColumn(format="dollar"),
                    "Return": st.column_config.NumberColumn(format="%.2f%%"),
                    "XIRR": st.column_config.NumberColumn(format="%.2f%%"),
                },
                key="compare_table",
            )
            with st.container(key="swipe_hint_compare"):
                st.caption(":material/swipe: Swipe the table sideways for more columns.")

ledger = res.ledger.assign(value_now=res.ledger["shares"] * prices.iloc[-1])
ledger["gain"] = ledger["value_now"] - ledger["amount"]
with st.expander("Purchase-by-purchase ledger", key="shadow_ledger"):
    st.dataframe(
        ledger,
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Spent on"),
            "description": "Merchant",
            "amount": st.column_config.NumberColumn("Amount", format="dollar"),
            "buy_date": st.column_config.DateColumn("Bought on"),
            "price": st.column_config.NumberColumn(f"{ticker} price", format="dollar"),
            "shares": st.column_config.NumberColumn("Shares", format="%.6f"),
            "value_now": st.column_config.NumberColumn("Worth now", format="dollar"),
            "gain": st.column_config.NumberColumn("Gain", format="dollar"),
        },
        key="ledger_table",
    )
st.caption("Past returns don't predict future returns. This is a what-if, not advice.")
