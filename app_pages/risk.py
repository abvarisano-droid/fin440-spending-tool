import pandas as pd
import streamlit as st

from core import lab, risk, ui
from core.portfolios import PRESETS
from core.prices import MARKET_PROXY, fetch_history, fetch_many, fetch_risk_free
from core.state import require_transactions, spending_only

st.title("Risk and CAPM")
st.caption(":material/school: FIN 440 link (Bodie, Kane & Marcus, 13e): Ch 2 (T-bill discount yield), Ch 5 (standard deviation, Sharpe ratio, drawdown), Ch 6 (risk-free vs. risky assets), Ch 7 (systematic vs. diversifiable risk), Ch 9 (CAPM, beta, alpha, the SML).")
st.caption(
    "How much each portfolio swung, and whether its return was fair pay for its market risk. "
    "Volatility and beta use a time-weighted unit value, so new purchases never look like "
    "returns. The market is SPY; the risk-free rate is the 13-week T-bill. Prices come from "
    "Yahoo Finance only."
)
spend = spending_only(require_transactions())

window = st.radio(
    "Measure risk over", ["purchases", "history"], horizontal=True, key="risk_window",
    format_func={"purchases": "Your purchase dates",
                 "history": "Last 5 years of fund history"}.get,
    help="Your purchase dates replay your actual buys (often only months of data, so beta and "
         "alpha are noisy). Fund history uses 5 years of daily prices with the same weights, "
         "rebalanced daily.",
)

names = list(PRESETS)
tickers = lab.tickers_for(names, (MARKET_PROXY,))
try:
    with st.spinner("Getting prices and the T-bill rate..."):
        rf = fetch_risk_free()
        if window == "purchases":
            prices = fetch_many(tickers, spend["date"].min())
        else:
            prices = {t: fetch_history(t, years=5) for t in tickers}
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

rf_annual = rf["effective_annual"]
market = prices[MARKET_PROXY].dropna()
if window == "purchases":
    ports = lab.preset_portfolios(spend, prices, names)
    series = {n: p.unit_value for n, p in ports.items()}
else:
    series = {n: lab.constant_mix_index(prices, PRESETS[n]) for n in names}
series[f"{MARKET_PROXY} (market)"] = market.loc[market.index >= series[names[0]].index[0]]

try:
    table = lab.risk_table(series, market, rf_annual)
except ValueError as exc:
    st.warning(f"Not enough overlapping trading days to measure risk yet ({exc}).")
    st.stop()

head = table.iloc[0]  # 100% VOO
alpha = head["alpha_annual"]
ui.kpi_row("risk_kpis", [
    dict(label="Volatility (yearly)", value=f"{head['ann_vol']:.1%}",
         help="Sample standard deviation of daily returns x sqrt(252)."),
    dict(label="Sharpe ratio", value=f"{head['sharpe']:.2f}",
         help="Average daily excess return over the T-bill, per unit of volatility, annualized."),
    dict(label="Max drawdown", value=f"{head['max_drawdown']:.1%}",
         help="Worst fall from a previous high."),
    dict(label="Beta vs SPY", value=f"{head['beta']:.2f}",
         help=f"Slope of excess returns on SPY's excess returns. R squared {head['r_squared']:.2f}, "
              f"{int(head['n'])} days."),
    dict(label="Alpha (yearly)", value=f"{alpha:+.2%}",
         delta=f"{'-' if alpha < 0 else '+'}{abs(alpha):.2%} vs CAPM",
         help="Jensen's alpha: the regression intercept on excess returns x 252. Positive = beat what its beta asked for."),
])
st.caption(
    f"For 100% VOO. Risk-free: 13-week T-bill at {rf['discount_yield']:.3%} discount yield = "
    f"{rf_annual:.2%} effective annual (as of {rf['as_of']:%b %d, %Y}). "
    f"{int(head['n'])} daily returns from {series[names[0]].index[0]:%b %d, %Y}."
    + (" Today's T-bill rate is applied to the whole window, a simplification: rates were near "
       "zero in 2021, so Sharpe and alpha are slightly understated." if window == "history" else "")
)
if head["n"] < 252:
    st.info(f"Only {int(head['n'])} trading days of purchases so far (under a year). Annualizing a short window "
            "exaggerates returns, and beta and alpha are noisy. Switch to fund history for a steadier read.")

mkt_ann = lab.market_annual_return(market, series[names[0]].index)
c1, c2 = st.columns(2)
with c1, ui.section("chart_risk_return", "Risk vs. return"):
    ui.chart_risk_return(table[["name", "ann_vol", "ann_return"]], key="risk_return_chart")
with c2, ui.section("chart_sml", "Security market line"):
    hi = max(1.6, float(table["beta"].max()) + 0.2)
    ui.chart_sml(risk.sml_line(rf_annual, mkt_ann, betas=[0.0, hi]),
                 table[["name", "beta", "ann_return"]], key="sml_chart")

with ui.section("risk_table", "All portfolios"):
    st.dataframe(
        table.assign(**{c: table[c] * 100 for c in ("ann_return", "ann_vol", "max_drawdown", "alpha_annual",
                                                    "capm_expected", "sml_gap")})
        [["name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "beta", "r_squared", "capm_expected",
          "sml_gap", "alpha_annual"]],
        hide_index=True,
        column_config={
            "name": "Portfolio",
            "ann_return": st.column_config.NumberColumn("Return", format="%.2f%%"),
            "ann_vol": st.column_config.NumberColumn("Volatility", format="%.2f%%"),
            "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "max_drawdown": st.column_config.NumberColumn("Max drawdown", format="%.2f%%"),
            "beta": st.column_config.NumberColumn("Beta", format="%.2f"),
            "r_squared": st.column_config.NumberColumn("R squared", format="%.2f"),
            "capm_expected": st.column_config.NumberColumn("CAPM expected", format="%.2f%%"),
            "sml_gap": st.column_config.NumberColumn("Above SML", format="%+.2f%%"),
            "alpha_annual": st.column_config.NumberColumn("Jensen's alpha", format="%+.2f%%"),
        },
        key="risk_stats",
    )

with ui.section("risk_explainer", "How to read this"):
    st.markdown(
        "**CAPM** says the return you should expect is set by market risk alone:"
    )
    st.latex(r"E[R_i] = r_f + \beta_i\,(E[R_m] - r_f)")
    st.markdown(
        f"Here $r_f$ = {rf_annual:.2%} (T-bill) and $E[R_m]$ = {mkt_ann:.2%} (SPY's realized annual "
        "return over the same days). The line on the right is that equation: the **security market "
        "line**. A dot above it earned more than its beta asked for over this window; below, less. "
        "SPY sits exactly on the line (beta 1, alpha 0), which is a built-in check.\n\n"
        + (f"**Why the line slopes down here:** over this window SPY returned {mkt_ann:.2%}, less "
           f"than the T-bill's {rf_annual:.2%}, so the realized market risk premium was negative "
           "and more beta was punished, not paid. That happens over short windows. CAPM is about "
           "*expected* returns, where the premium is positive; switch to 5 years of fund history "
           "to see the usual upward line.\n\n" if mkt_ann < rf_annual else "")
        + "**Two alphas, on purpose.** *Above SML* is the dot's vertical distance from the line, using "
        "compounded (geometric) returns. *Jensen's alpha* is the regression intercept on daily excess "
        "returns, times 252 (arithmetic). They are close and usually share a sign, but they are not identical.\n\n"
        "**Diversification:** BND has a low beta, so the 60/40 mix lowers volatility and beta "
        "together. The share of variance beta does not explain (1 minus R squared) is diversifiable, and "
        "CAPM says the market does not pay you for carrying it."
    )
