import streamlit as st

from core import ui
from core.categorize import ALL_CATEGORIES
from core.prices import clean_ticker, fetch_adjusted_close
from core.state import require_transactions, spending_only
from core.timing import timing_test

N_SHUFFLES = 1000

st.title("Timing test")
st.caption(
    "If prices already reflect everything knowable, the days you happened to spend should look "
    "like luck. This replays your purchases on 1,000 random sets of days and ranks your real dates."
)
tx = spending_only(require_transactions())

c1, c2 = st.columns([1, 2])
raw = c1.text_input("Fund ticker", value="VOO", max_chars=10, key="timing_ticker")
present = [c for c in ALL_CATEGORIES if c in set(tx["category"])]
cats = c2.multiselect("Categories", present, default=present, key="timing_cats")

ticker = clean_ticker(raw)
if ticker is None:
    st.error("That doesn't look like a ticker. Use letters, numbers, dots or dashes.")
    st.stop()
spend = tx[tx["category"].isin(cats)]
if spend.empty:
    st.warning("Pick at least one category.")
    st.stop()

try:
    with st.spinner(f"Getting {ticker} prices..."):
        prices = fetch_adjusted_close(ticker, spend["date"].min())
    res = timing_test(spend, prices, n_shuffles=N_SHUFFLES, seed=0)
except (RuntimeError, ValueError) as exc:
    st.error(str(exc))
    st.stop()


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


pct = round(res["percentile"] * 100)
ui.kpi_row("timing_kpis", [
    dict(label=f"Your dates, in {ticker}", value=f"${res['actual_value']:,.2f}",
         help="Each purchase buys at the close of the first trading day on or after it, valued today."),
    dict(label="Median random dates", value=f"${res['median_shuffled']:,.2f}",
         help=f"Median of {N_SHUFFLES:,} reshuffles. Each purchase moves to a random trading day "
              "between your first and last buy."),
    dict(label=f"Your percentile, of {N_SHUFFLES:,} shuffles", value=f"{ordinal(pct)}",
         help=f"Share of the {N_SHUFFLES:,} reshuffles your real dates beat (ties count half)."),
])

with ui.section("chart_timing_hist", f"{N_SHUFFLES:,} random sets of purchase days"):
    ui.chart_histogram(
        res["shuffled_values"],
        markers=[
            dict(label="Your dates", value=res["actual_value"], color=ui.ACCENT),
            dict(label="Median random", value=res["median_shuffled"], color=ui.MUTED, dashed=True),
        ],
        x_title=f"Value today in {ticker} ($)",
        key="timing_hist",
    )

luck = 5 <= pct <= 95
invested = spend["amount"].sum()
with ui.section("timing_explainer", "What this says"):
    st.markdown(
        f"Your real dates beat **{res['percentile']:.0%}** of {N_SHUFFLES:,} random ones "
        f"(two-sided p-value {res['p_value_two_sided']:.2f}). "
        + ("Anywhere from the 5th to the 95th percentile is what luck looks like, so this is "
           "**consistent with market efficiency**: when you spent told the market nothing."
           if luck else
           "That is outside the 5th to 95th percentile band. Over a short window one big market "
           "move can do this; it is not evidence of skill unless it repeats out of sample.")
        + f"\n\nFor scale: putting all \\${invested:,.2f} in on your first buy day would be worth "
          f"**\\${res['lump_sum_value']:,.2f}** today. In a rising market, money that goes in earlier "
          "has longer to grow, so lump sum tends to beat spreading purchases out. That is a drift "
          "effect, not timing skill.\n\n"
        f"Method: {res['trading_days_used']} trading days in your purchase window, "
        f"{N_SHUFFLES:,} shuffles, fixed seed {res['seed']} so the numbers reproduce."
    )
