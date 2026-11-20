import altair as alt
import pandas as pd
import streamlit as st

from core import invest, lab, ui
from core.categorize import ALL_CATEGORIES, DISCRETIONARY
from core.portfolios import PRESETS
from core.prices import clean_ticker, fetch_adjusted_close, fetch_many
from core.shadow import build_shadow
from core.state import discretionary_monthly, require_transactions, spending_only
from core.suggest import suggest_monthly

ui.page_header(
    "Shadow portfolio",
    course="FIN 440 link (Bodie, Kane & Marcus, 13e): Ch 2 (asset classes, stock and bond indexes), Ch 5 (holding-period returns, compounding), Ch 7 (stock-bond diversification).",
    lede=(
        "What if every want (dining, coffee, shopping and the rest) had bought an index fund instead? Each dollar buys fractional "
        "shares at the close of the first trading day on or after the purchase. Prices are "
        "dividend-adjusted, so dividends count as reinvested. No fees or taxes. Only the ticker and "
        "your earliest purchase date go to Yahoo Finance."
    ),
)
tx = spending_only(require_transactions())

with ui.section("shadow_controls"):
    QUICK = {"VOO": "S&P 500", "SCHD": "Dividend", "XLV": "Health care", "QQQ": "Nasdaq 100", "GLD": "Gold"}
    if "shadow_ticker" not in st.session_state:
        st.session_state["shadow_ticker"] = "VOO"

    def _pick_fund():
        if st.session_state.get("shadow_chip"):
            st.session_state["shadow_ticker"] = st.session_state["shadow_chip"]

    st.pills("Try a fund", list(QUICK), format_func=lambda t: f"{t} · {QUICK[t]}", key="shadow_chip",
             on_change=_pick_fund)
    c1, c2 = st.columns([1, 2])
    raw_ticker = c1.text_input("Fund ticker", max_chars=10, key="shadow_ticker",
                               help="Any Yahoo Finance ticker, e.g. VOO, VTI, QQQ, SCHD.")
    present = [c for c in ALL_CATEGORIES if c in DISCRETIONARY and c in set(tx["category"])]
    if not present:
        st.info("No discretionary (wants) spending found: dining, coffee, entertainment, shopping, "
                "subscriptions or travel. Fix categories on the Spending page.")
        st.stop()
    cats = c2.multiselect("Wants to shadow", present, default=present, key="shadow_cats",
                          help="Only discretionary spending: the money you chose to spend, and could have "
                               "invested instead. Needs like groceries, gas and bills stay out.")
    i1, i2 = st.columns([1, 2])
    mode = invest.mode_radio(i1, "shadow",
                             help="Percent of wants: each purchase invests that share of itself, on the day you "
                                  "spent it. Exact $ per month: the same amount buys on the 1st of every month, "
                                  "whatever you spent. The Roth page uses the same choice.")
    if mode == invest.PERCENT:
        share_pct = i2.slider("Share of each want", 5, 100, 100, 5, format="%d%%", key="shadow_pct",
                              help="100% = every want dollar is invested instead.")
    else:
        dollars = invest.dollars_input(i2, "shadow", suggest_monthly(discretionary_monthly(tx)).monthly)

ticker = clean_ticker(raw_ticker)
if ticker is None:
    st.error("That doesn't look like a ticker. Use letters, numbers, dots or dashes.")
    st.stop()
spend = tx[tx["category"].isin(cats)]
if spend.empty:
    st.warning("Pick at least one category.")
    st.stop()
# what actually buys the fund: a share of each want on its own date, or a fixed amount every month
if mode == invest.PERCENT:
    buys = invest.scale_purchases(spend, share_pct / 100)
    plan = "every want" if share_pct == 100 else f"{share_pct}% of every want"
else:
    buys = invest.monthly_buys(spend, dollars)
    plan = f"\\${dollars:,.0f} on the 1st of each month ({len(buys)} months)"

with st.spinner(f"Getting {ticker} prices..."):
    try:
        prices = fetch_adjusted_close(ticker, buys["date"].min())
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

res = build_shadow(buys, prices)

ui.kpi_row("shadow_kpis", [
    dict(label="You spent" if mode == invest.PERCENT and share_pct == 100 else "You put in",
         value=f"${res.invested:,.2f}"),
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

st.caption(f":material/payments: Investing {plan}, out of \\${spend['amount'].sum():,.2f} of wants.")
if res.skipped:
    st.info(f"{res.skipped} purchase(s) are after the latest {ticker} close and are left out.")

timeline = res.timeline.melt("date", ["invested", "value"], var_name="series", value_name="dollars")
timeline["series"] = timeline["series"].map({"invested": "Spent (cumulative)", "value": f"Value in {ticker}"})
with ui.section("chart_shadow", "Spent vs. shadow value"):
    ui.chart(
        alt.Chart(timeline)
        .mark_line(interpolate="step-after")
        .encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %-d", labelOverlap=True)),
            y=alt.Y("dollars:Q", title="Dollars"),
            color=alt.Color("series:N", title=None),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("series:N", title="Series"),
                     alt.Tooltip("dollars:Q", title="Dollars", format="$,.2f")],
        ),
    )

with ui.section("shadow_compare", "Same purchases, four portfolios"):
    picks = st.multiselect("Portfolios", list(PRESETS), default=list(PRESETS), max_selections=4,
                           key="compare_pick")
    if picks:
        try:
            with st.spinner("Getting fund prices..."):
                cmp_prices = fetch_many(lab.tickers_for(picks), buys["date"].min())
            ports = lab.preset_portfolios(buys, cmp_prices, picks)
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
        else:
            lines = pd.concat([p.timeline.assign(name=n) for n, p in ports.items()])
            ui.chart(
                alt.Chart(lines)
                .mark_line(interpolate="step-after")
                .encode(
                    x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %-d", labelOverlap=True)),
                    y=alt.Y("value:Q", title="Value ($)"),
                    color=alt.Color("name:N", title=None),
                    tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("name:N", title="Portfolio"),
                             alt.Tooltip("value:Q", title="Value", format="$,.2f")],
                ),
                key="compare_chart",
            )
            st.dataframe(
                pd.DataFrame([{
                    "Portfolio": n, "Worth now": p.value, "Gain": p.gain, "Put in": p.invested,
                    "Return": p.simple_return * 100,
                    "XIRR": p.xirr * 100 if p.xirr is not None else None,
                } for n, p in ports.items()]),
                hide_index=True,
                column_config={
                    "Put in": st.column_config.NumberColumn(format="dollar"),
                    "Worth now": st.column_config.NumberColumn(format="dollar"),
                    "Gain": st.column_config.NumberColumn(format="dollar"),
                    "Return": st.column_config.NumberColumn(format="%.2f%%"),
                    "XIRR": st.column_config.NumberColumn(format="%.2f%%"),
                },
                key="compare_table",
            )
            with st.container(key="swipe_hint_compare"):
                st.caption(":material/swipe: Swipe the table sideways for more columns.")
    st.caption("Each purchase is split across funds by fixed weights and held, no rebalancing. "
               "Diversification in practice: compare how far each line swings, not only where it ends.")
    st.caption(":material/casino: Over a few months, which fund wins is mostly luck: a dividend fund can be up "
               "while the S&P 500 is down, and the order flips in other windows. The Roth page uses "
               "long-run averages for that reason.")

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
