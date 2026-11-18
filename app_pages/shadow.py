import altair as alt
import streamlit as st

from core import ui
from core.categorize import ALL_CATEGORIES
from core.prices import clean_ticker, fetch_adjusted_close
from core.shadow import build_shadow
from core.state import require_transactions, spending_only

st.title("Shadow portfolio")
st.caption(
    "What if every purchase had bought an index fund instead? Each dollar buys fractional "
    "shares at the close of the first trading day on or after the purchase. Prices are "
    "dividend-adjusted, so dividends count as reinvested. No fees or taxes."
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
         delta=f"${res.gain:,.2f} ({res.simple_return:+.2%})"),
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

ledger = res.ledger.assign(value_now=res.ledger["shares"] * prices.iloc[-1])
ledger["gain"] = ledger["value_now"] - ledger["amount"]
with st.expander("Purchase-by-purchase ledger", key="shadow_ledger"):
    st.dataframe(
        ledger,
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Spent on"),
            "description": "Merchant",
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "buy_date": st.column_config.DateColumn("Bought on"),
            "price": st.column_config.NumberColumn(f"{ticker} price", format="$%.2f"),
            "shares": st.column_config.NumberColumn("Shares", format="%.6f"),
            "value_now": st.column_config.NumberColumn("Worth now", format="$%.2f"),
            "gain": st.column_config.NumberColumn("Gain", format="$%.2f"),
        },
        key="ledger_table",
    )
st.caption("Past returns don't predict future returns. This is a what-if, not advice.")
