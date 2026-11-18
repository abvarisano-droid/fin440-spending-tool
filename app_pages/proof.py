import streamlit as st

from core import lab, proof, ui
from core.prices import MARKET_PROXY, fetch_many, fetch_risk_free
from core.state import SAMPLE_CSV, require_transactions, spending_only

st.title("Proof")
st.caption(
    "Every number in this app is checked live against a second, independent computation, and "
    "the workbook below lets you redo the math in Excel with real formulas."
)
tx = require_transactions()
spend = spending_only(tx)
is_sample = st.session_state.get("source_name", "").startswith("Sample")

try:
    with st.spinner("Getting prices and running checks..."):
        rf = fetch_risk_free()
        prices = fetch_many(["VOO", MARKET_PROXY], spend["date"].min())
        checks = proof.run_checks(tx, spend, prices["VOO"], prices[MARKET_PROXY], rf["effective_annual"],
                                  sample_path=SAMPLE_CSV if is_sample else None)
except (RuntimeError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

passed = sum(c.passed for c in checks)
with ui.section("proof_checks", "Live checks"):
    st.markdown(f"**{passed} of {len(checks)} checks pass** on your data and today's prices.")
    st.dataframe(proof.checks_frame(checks), hide_index=True, key="proof_table",
                 column_config={"How": st.column_config.TextColumn("How it's checked", width="large")})

by_name = {c.name: c for c in checks}
risk_row = lab.risk_table(
    {"VOO": prices["VOO"].loc[prices["VOO"].index >= spend["date"].min()]},
    prices[MARKET_PROXY], rf["effective_annual"]).iloc[0]
workbook = proof.build_workbook(
    spend, prices["VOO"], prices[MARKET_PROXY], rf["discount_yield"],
    app=dict(
        shadow_value=by_name["Shadow: VOO value vs a brute-force loop"].app,
        beta=by_name["Beta: regression vs cov/var"].app,
        vol=by_name["Volatility: app vs numpy"].app,
        sharpe=float(risk_row["sharpe"]),
        rf_effective=rf["effective_annual"],
        roth_fv=by_name["Roth: app vs a month-by-month loop"].app,
    ),
)
with ui.section("proof_download", border=False):
    st.download_button(
        "Download the cross-check workbook", workbook, file_name="spend-shadow-cross-check.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary",
        icon=":material/download:", key="proof_xlsx",
    )
    st.caption("Built in memory from your session; nothing is saved on the server. Sheets: Roth (FV), "
               "Shadow (every purchase, shares and value), Risk (SLOPE beta, volatility, T-bill, Sharpe).")

with st.expander("How AI built this, and how we kept it honest", key="proof_process"):
    st.markdown(
        """
**Who did what.** Three AI agents with separate jobs and separate files, coordinated by a written
rulebook (`AGENTS.md`) and an append-only log (`HANDOFF.md`):
- **Builder (Claude Code):** app logic, math engines and tests.
- **Designer (Grok):** the look: design system, theme, CSS and chart helpers.
- **Auditor:** reviews each phase and doesn't fix. Grok audits the builder's phases, and a fresh
  Claude session audits Grok's, so nobody grades their own work.

**How each number was verified.** Every engine has hand-worked tests with expected values computed
outside the code (Excel `FV`, hand formulas, brute-force loops). Each phase was then re-checked
independently by the auditor, and this page re-runs the key checks live on your data.

**What the audits caught** (all fixed before shipping):
- The Roth cap ignored the age-50 catch-up contribution.
- A loss on the shadow portfolio displayed green, because of how the sign was formatted.
- Dollar signs in text were being rendered as math formulas.
- The chart palette had fewer colors than spending categories, so two categories shared a color.
- Over a short window the security market line sloped downward with no explanation (the market
  earned less than T-bills); the page now says why.

**What AI did not decide.** The scope, the class topics, every "fix or document" call and
what ships were human decisions. The AI wrote code and checks; people read the results.
"""
    )
