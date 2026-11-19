import streamlit as st

from core import proof, ui
from core.prices import fetch_many
from core.state import SAMPLE_CSV, discretionary_monthly, require_transactions, spending_only

st.title("Proof")
st.caption(
    "The key numbers are checked live against a second computation that doesn't use the app's own "
    "code (the Monte Carlo row instead confirms that two of the app's engines agree), "
    "and the workbook below "
    "lets you redo the math in Excel with real formulas."
)
tx = require_transactions()
spend = spending_only(tx)
is_sample = st.session_state.get("source_name", "").startswith("Sample")

try:
    with st.spinner("Getting prices and running checks..."):
        prices = fetch_many(["VOO", "BND"], spend["date"].min())
        checks = proof.run_checks(tx, spend, prices["VOO"], sample_path=SAMPLE_CSV if is_sample else None,
                                  bnd=prices["BND"], disc_monthly=discretionary_monthly(spend))
except (RuntimeError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

passed = sum(c.passed for c in checks)
with ui.section("proof_checks", "Live checks"):
    st.markdown(f"**{passed} of {len(checks)} checks pass** on your data and today's prices.")
    st.dataframe(proof.checks_frame(checks), hide_index=True, key="proof_table",
                 column_order=["Result", "App", "Check", "Difference", "Independent"],
                 column_config={"Result": st.column_config.TextColumn("Result", width="small"),
                                "Check": st.column_config.TextColumn("Check", width="large")})
    with st.container(key="swipe_hint_proof"):
        st.caption(":material/swipe: Swipe the table sideways for more columns.")
    with st.expander("How each check is computed", key="proof_how"):
        st.markdown(proof.how_list(checks))
    st.caption(
        ("" if is_sample else "The spending-total check runs on the sample only, because your raw file "
         "isn't kept. ")
        + "Not live-checked here, but recomputed by hand in the final audit: XIRR, the BND and QQQ "
        "portfolios and the Monte Carlo percentiles."
    )

by_name = {c.name: c for c in checks}
workbook = proof.build_workbook(
    spend, prices["VOO"],
    app=dict(
        shadow_value=by_name["Shadow: VOO value vs a brute-force loop"].app,
        roth_fv=by_name["Roth: app vs Excel FV(7%/12, 528, -200)"].app,
    ),
)
with ui.section("proof_download", border=False):
    st.download_button(
        "Download the cross-check workbook", workbook, file_name="spend-shadow-cross-check.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary",
        icon=":material/download:", key="proof_xlsx",
    )
    st.caption("Built in memory from your session; nothing is saved on the server. Sheets: Roth (FV) and "
               "Shadow (every purchase, shares and value).")

with st.expander("How AI built this, and how we kept it honest", key="proof_process"):
    st.markdown(
        """
**Who did what.** Three AI agents with separate jobs and separate files, coordinated by a written
rulebook (`AGENTS.md`) and an append-only log (`HANDOFF.md`):
- **Builder (Claude Code):** app logic, math engines and tests.
- **Designer (Grok):** the look: design system, theme, CSS and chart helpers.
- **Auditor:** a separate, read-only Claude session reviews each phase and doesn't fix, so nobody
  grades their own work. Grok also audited some of the builder's earlier phases.

**How each number was verified.** Every engine has hand-worked tests with expected values computed
outside the code (Excel `FV`, hand formulas, brute-force loops). Each phase was then re-checked
independently by the auditor, and this page re-runs the key checks live on your data.

**What the audits caught** (all fixed before shipping):
- The Roth cap ignored the age-50 catch-up contribution.
- A loss on the shadow portfolio displayed green, because of how the sign was formatted.
- Dollar signs in text were being rendered as math formulas.
- The chart palette had fewer colors than spending categories, so two categories shared a color.
- One Proof check compared an engine with itself; it was replaced with an independent recompute.

**What AI did not decide.** The scope, the class topics, every "fix or document" call and
what ships were human decisions. The AI wrote code and checks; people read the results.
"""
    )
