import altair as alt
import streamlit as st

from core import montecarlo, tvm, ui
from core.prices import clean_ticker, fetch_history
from core.state import get_transactions, spending_only

st.title("Roth IRA calculator")
st.caption(":material/school: FIN 440 link (Bodie, Kane & Marcus, 13e): Ch 5 (compounding, APR vs. EAR, real vs. nominal returns, arithmetic vs. geometric averages).")
st.caption(
    "Monthly contributions grow tax-free. Use a real (after-inflation) return to read every "
    "number in today's dollars. Roth eligibility has income limits, which this calculator "
    "doesn't check."
)

tx = get_transactions()
disc_monthly = None
if tx is not None and not tx.empty:
    s = spending_only(tx)
    months = max(s["date"].dt.to_period("M").nunique(), 1)
    disc_monthly = s.loc[s["discretionary"], "amount"].sum() / months

with ui.section("roth_inputs"):
    c1, c2, c3 = st.columns(3)
    with c1:
        current_age = st.number_input("Current age", 16, 80, 21, key="roth_age")
        retirement_age = st.number_input("Retirement age", 17, 90, 65, key="roth_retire")
        starting = st.number_input("Current Roth balance ($)", 0.0, 10_000_000.0, 0.0, step=100.0,
                                   key="roth_start")
    with c2:
        sources = ["Enter an amount"] + (["Redirect discretionary spending"] if disc_monthly else [])
        source = st.radio("Monthly contribution", sources, key="roth_source")
        if source == "Enter an amount":
            monthly = st.number_input("Per month ($)", 0.0, 10_000.0, 200.0, step=25.0, key="roth_monthly")
        else:
            pct = st.slider("Share of discretionary spending to redirect", 0, 100, 25, 5,
                            format="%d%%", key="roth_pct")
            monthly = disc_monthly * pct / 100
            st.caption(f"Your discretionary average is \\${disc_monthly:,.2f}/month, so this redirects "
                       f"**\\${monthly:,.2f}/month**.")
    with c3:
        rate_pct = st.slider("Annual return", 0.0, 12.0, 7.0, 0.25, format="%.2f%%", key="roth_rate",
                             help="7% is a common long-run real return assumption for US stocks.")
        convention = st.radio(
            "Rate convention", ["apr", "effective"], key="roth_conv",
            format_func={"apr": "APR, monthly compounding (r/12)",
                         "effective": "Effective annual rate"}.get,
        )
        due = st.toggle("Contribute at the start of each month", value=False, key="roth_due",
                        help="Off = ordinary annuity (end of month). On = annuity due.")
        enforce = st.toggle("Cap at the IRA limit", value=True, key="roth_cap",
                            help=f"2026: \\${tvm.IRA_LIMIT_2026:,.0f}/yr, plus \\${tvm.IRA_CATCHUP_2026:,.0f} "
                                 f"from age {tvm.CATCHUP_AGE}. Held flat in today's dollars.")

if retirement_age <= current_age:
    st.error("Retirement age must be after current age.")
    st.stop()

proj = tvm.roth_projection(int(current_age), int(retirement_age), monthly, rate_pct / 100,
                           starting, convention, due, enforce)
final = proj.iloc[-1]
years = int(retirement_age - current_age)
pmts = tvm.monthly_payments_by_age(int(current_age), int(retirement_age), monthly, enforce)
capped = any(p < monthly for p in pmts)
put_in = final["total_contributed"] + starting

ui.kpi_row("roth_kpis", [
    dict(label=f"Balance at {int(retirement_age)}", value=f"${final['balance']:,.0f}"),
    dict(label="You put in", value=f"${put_in:,.0f}"),
    dict(label="Growth", value=f"${final['growth']:,.0f}",
         delta=f"+{final['growth'] / put_in:.0%} on contributions" if put_in > 0 else None,
         help="Growth divided by everything you put in (contributions plus starting balance)."),
])
if capped:
    capped_ages = [a for a, p in zip(range(int(current_age), int(retirement_age)), pmts) if p < monthly]
    st.info(f"\\${monthly:,.2f}/month is over the IRA limit at ages {capped_ages[0]} to {capped_ages[-1]}, "
            f"so those years use the cap: \\${tvm.IRA_LIMIT_2026 / 12:,.2f}/month before {tvm.CATCHUP_AGE}, "
            f"\\${tvm.annual_limit(tvm.CATCHUP_AGE) / 12:,.2f}/month from {tvm.CATCHUP_AGE} (catch-up).")

chart_df = proj.assign(principal=proj["total_contributed"] + starting)[["age", "principal", "growth"]]
chart_df = chart_df.melt("age", var_name="part", value_name="dollars")
chart_df["part"] = chart_df["part"].map({"principal": "Contributions", "growth": "Growth"})
with ui.section("chart_roth", "Balance by age"):
    ui.chart(
        alt.Chart(chart_df)
        .mark_area()
        .encode(
            x=alt.X("age:Q", title="Age", scale=alt.Scale(zero=False)),
            y=alt.Y("dollars:Q", title="Dollars", stack=True),
            color=alt.Color("part:N", title=None, sort=["Contributions", "Growth"]),
            order=alt.Order("part:N", sort="ascending"),
            tooltip=[alt.Tooltip("age:Q", title="Age"), alt.Tooltip("part:N", title=""),
                     alt.Tooltip("dollars:Q", title="Dollars", format="$,.0f")],
        ),
    )

r = tvm.periodic_rate(rate_pct / 100, 12, convention)
n = years * 12


def _simulate(*args, **kwargs):
    """Memoized per browser session, not in st.cache_data: the inputs can be derived from the
    upload (redirected spending), and st.cache_data is shared by every visitor on the server."""
    key = repr((args, sorted((k, v.tobytes() if hasattr(v, "tobytes") else v) for k, v in kwargs.items())))
    memo = st.session_state.setdefault("_mc_memo", {})
    if key not in memo:
        if len(memo) >= 10:
            memo.clear()
        memo[key] = montecarlo.simulate_roth(*args, **kwargs)
    return memo[key]


with ui.section("roth_mc_controls", "With uncertain returns"):
    st.caption("The chart above earns the same return every month. Real markets don't. Here every "
               "month draws a random return with the same average, thousands of times.")
    m1, m2, m3, m4 = st.columns(4)
    method = m1.radio("Returns", ["normal", "bootstrap"], key="mc_method",
                      format_func={"normal": "Normal (pick the volatility)",
                                   "bootstrap": "Replay real fund months"}.get)
    if method == "normal":
        vol_pct = m2.slider("Yearly volatility", 0.0, 40.0, 15.0, 0.5, format="%.1f%%", key="mc_vol",
                            help="About 15% is typical for a broad US stock index.")
    else:
        mc_raw = m2.text_input("Fund for history", value="VOO", max_chars=10, key="mc_ticker")
    target = m3.number_input("Target balance ($)", 0.0, 100_000_000.0,
                             float(round(final["balance"], -3)), step=10_000.0, key="mc_target",
                             help="Defaults to the fixed-return balance above.")
    n_sims = m4.selectbox("Simulations", [1000, 5000, 10000], index=1, key="mc_sims")

mc_kwargs = dict(n_sims=n_sims, seed=0, due=due, enforce_limit=enforce)
history_note = ""
if method == "normal":
    # same average monthly rate as the fixed-return chart, so the mean lines up with it
    mc = _simulate(int(current_age), int(retirement_age), monthly, starting, method="normal",
                   annual_mean=r * 12, annual_vol=vol_pct / 100, **mc_kwargs)
else:
    mc_ticker = clean_ticker(mc_raw)
    if mc_ticker is None:
        st.error("That doesn't look like a ticker.")
        st.stop()
    try:
        with st.spinner(f"Getting 10 years of {mc_ticker}..."):
            hist = montecarlo.monthly_returns_from_prices(fetch_history(mc_ticker, years=10))
        mc = _simulate(int(current_age), int(retirement_age), monthly, starting, method="bootstrap",
                       history=hist.to_numpy(), **mc_kwargs)
    except (RuntimeError, ValueError) as exc:
        st.error(str(exc))
        st.stop()
    history_note = (f" Bootstrap draws from {len(hist)} real {mc_ticker} months "
                    f"(average {hist.mean():.2%}/month). Those are nominal returns, so this view is "
                    "in future dollars, not today's.")

pcts = mc["percentiles"]
with ui.section("chart_roth_fan", "Range of outcomes by age"):
    ui.chart_fan(pcts, key="roth_fan")
    st.caption("Outer band: 5th to 95th percentile. Inner band: 25th to 75th. Line: median.")

end = pcts.iloc[-1]
odds = montecarlo.prob_reaching(mc["final"], target)
ui.kpi_row("roth_mc_kpis", [
    dict(label=f"Median at {int(retirement_age)}", value=f"${end['p50']:,.0f}",
         help="Half the simulations end above this, half below."),
    dict(label="Bad case (5th percentile)", value=f"${end['p5']:,.0f}",
         help="1 in 20 simulations ends below this."),
    dict(label=f"Odds of reaching \\${target:,.0f}", value=f"{odds:.0%}",
         help="Share of simulations at or above the target."),
])
closed = montecarlo.expected_fv_closed_form(int(current_age), int(retirement_age), monthly, starting,
                                            r * 12, due, enforce)
st.caption(
    f"Check: the average of {mc['n_sims']:,} runs is \\${mc['mean_final']:,.0f}"
    + (f", vs \\${closed:,.0f} from the fixed-return formula. They should be close, since the "
       "average return is the same. The median sits below the average because losses compound: "
       "-50% then +50% leaves you at 75%, not 100% (volatility drag)." if method == "normal" else
       ".")
    + history_note
)
with st.expander("Show the math", key="roth_math"):
    fv, segments = tvm.fv_segments(starting, pmts, r, due)
    due_term = r"\cdot(1+r)" if due else ""
    if len(segments) == 1:
        st.latex(r"FV = PV(1+r)^n + PMT\cdot\frac{(1+r)^n - 1}{r}" + due_term)
    else:
        st.write("The payment changes partway (IRA cap and age-50 catch-up), so each run of equal "
                 "payments is its own annuity, grown to retirement for the months after it ends:")
        st.latex(r"FV = PV(1+r)^n + \sum_k PMT_k\cdot\frac{(1+r)^{n_k} - 1}{r}" + due_term
                 + r"\cdot(1+r)^{m_k}")
    lines = [f"r = {r:.6%} per month, n = {n} months, PV = \\${starting:,.2f}",
             f"FV of PV = \\${tvm.fv_lump(starting, r, n):,.2f}"]
    for pmt, months, after in segments:
        lines.append(f"PMT = \\${pmt:,.2f} for {months} months, then grows {after} months: "
                     f"\\${tvm.fv_annuity(pmt, r, months, due) * (1 + r) ** after:,.2f}")
    lines.append(f"**Total FV = \\${fv:,.2f}** (matches the balance above)")
    st.markdown("  \n".join(lines))
    st.dataframe(
        proj,
        hide_index=True,
        column_config={
            "age": "Age",
            "contributed_this_year": st.column_config.NumberColumn("Added that year", format="$%.0f"),
            "total_contributed": st.column_config.NumberColumn("Total added", format="$%.0f"),
            "balance": st.column_config.NumberColumn("Balance", format="$%.0f"),
            "growth": st.column_config.NumberColumn("Growth", format="$%.0f"),
        },
        key="roth_table",
    )
