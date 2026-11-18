import altair as alt
import streamlit as st

from core import tvm, ui
from core.state import get_transactions, spending_only

st.title("Roth IRA calculator")
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
            st.caption(f"Your discretionary average is ${disc_monthly:,.2f}/month, so this redirects "
                       f"**${monthly:,.2f}/month**.")
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
                            help=f"2026: ${tvm.IRA_LIMIT_2026:,.0f}/yr, plus ${tvm.IRA_CATCHUP_2026:,.0f} "
                                 f"from age {tvm.CATCHUP_AGE}. Held flat in today's dollars.")

if retirement_age <= current_age:
    st.error("Retirement age must be after current age.")
    st.stop()

proj = tvm.roth_projection(int(current_age), int(retirement_age), monthly, rate_pct / 100,
                           starting, convention, due, enforce)
final = proj.iloc[-1]
years = int(retirement_age - current_age)
capped = enforce and monthly > tvm.IRA_LIMIT_2026 / 12

ui.kpi_row("roth_kpis", [
    dict(label=f"Balance at {int(retirement_age)}", value=f"${final['balance']:,.0f}"),
    dict(label="You put in", value=f"${final['total_contributed'] + starting:,.0f}"),
    dict(label="Growth", value=f"${final['growth']:,.0f}"),
])
if capped:
    st.info(f"${monthly:,.2f}/month is over the IRA limit, so contributions are capped at "
            f"${tvm.IRA_LIMIT_2026 / 12:,.2f}/month (more after {tvm.CATCHUP_AGE}).")

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
with st.expander("Show the math", key="roth_math"):
    if enforce and capped:
        st.write("Contributions hit the cap, so the closed form below uses the capped payment "
                 "and only matches the simulation exactly if the cap never changes (no catch-up years).")
    pmt = min(monthly, tvm.IRA_LIMIT_2026 / 12) if enforce else monthly
    st.latex(r"FV = PV(1+r)^n + PMT\cdot\frac{(1+r)^n - 1}{r}" + (r"\cdot(1+r)" if due else ""))
    st.write(
        f"r = {r:.6%} per month, n = {n} months, PMT = ${pmt:,.2f}, PV = ${starting:,.2f}  \n"
        f"FV of PV = ${tvm.fv_lump(starting, r, n):,.2f}  \n"
        f"FV of payments = ${tvm.fv_annuity(pmt, r, n, due):,.2f}"
    )
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
