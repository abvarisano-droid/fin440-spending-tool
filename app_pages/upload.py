from pathlib import Path

import streamlit as st

from core import ingest, ui
from core.categorize import categorize
from core.state import SAMPLE_CSV, clear_transactions, get_transactions, set_transactions, spending_only

st.title("Upload your transactions")
st.caption(
    "Export a CSV from your bank or card. Your transactions stay in this browser session only: "
    "they're never saved to disk or sent anywhere. Only purchases count as spending; refunds, "
    "deposits and other money coming in are left out, not subtracted."
)

with ui.section("upload_source", border=False):
    uploaded = st.file_uploader("Bank or card CSV", type=["csv"], key="csv_file")
    use_sample = st.button("Use sample data", icon=":material/science:", key="use_sample")

if use_sample:
    # known format, so skip the mapper and load in one click
    sample = ingest.read_csv(SAMPLE_CSV)
    m = ingest.detect_columns(sample)
    set_transactions(
        categorize(ingest.normalize(sample, m, ingest.guess_purchases_negative(sample, m))),
        "Sample data (fictional)",
    )

if uploaded is not None:
    try:
        raw = ingest.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Couldn't read that file as CSV: {exc}")
        st.stop()
    source = uploaded.name
else:
    raw = source = None

if raw is not None:
    if raw.empty:
        st.error("That file has no rows.")
        st.stop()

    detected = ingest.detect_columns(raw)
    cols = list(raw.columns)
    none_opt = ["(none)"]

    def pick(label, current, key, allow_none=False):
        options = (none_opt if allow_none else []) + cols
        index = options.index(current) if current in options else 0
        choice = st.selectbox(label, options, index=index, key=key)
        return None if choice == "(none)" else choice

    with ui.section("column_mapper", "Check the columns"):
        st.caption("Auto-detected. Fix any that look wrong.")
        c1, c2, c3 = st.columns(3)
        with c1:
            date_col = pick("Date", detected.date, "map_date")
            desc_col = pick("Description", detected.description, "map_desc")
        with c2:
            mode = st.radio(
                "Amounts are in",
                ["One amount column", "Separate debit and credit columns"],
                index=1 if detected.debit else 0,
                key="map_mode",
            )
            if mode == "One amount column":
                amount_col = pick("Amount", detected.amount, "map_amount")
                debit_col = credit_col = None
            else:
                amount_col = None
                debit_col = pick("Debit (money out)", detected.debit, "map_debit")
                credit_col = pick("Credit (money in)", detected.credit, "map_credit", allow_none=True)
        with c3:
            mapping = ingest.ColumnMap(date_col, desc_col, amount_col, debit_col, credit_col)
            if amount_col:
                guess = ingest.guess_purchases_negative(raw, mapping)
                sign = st.radio(
                    "Purchases show up as",
                    ["Negative numbers", "Positive numbers"],
                    index=0 if guess else 1,
                    key="map_sign",
                    help="Chase and most banks use negative for purchases. Amex and Discover use positive.",
                )
                purchases_negative = sign == "Negative numbers"
            else:
                purchases_negative = False

    st.dataframe(raw.head(5), hide_index=True, key="raw_preview")

    if st.button("Load transactions", type="primary", icon=":material/check:", key="load_btn"):
        try:
            tx = categorize(ingest.normalize(raw, mapping, purchases_negative))
        except Exception as exc:
            st.error(f"Couldn't parse with that mapping: {exc}")
            st.stop()
        if tx.empty:
            st.error("No spending rows found. Try flipping 'Purchases show up as'.")
            st.stop()
        set_transactions(tx, source)
        st.success(f"Loaded {len(tx):,} purchases from {source}.")

tx = get_transactions()
if tx is not None:
    spend = spending_only(tx)
    with ui.section("loaded_summary", "Loaded"):
        ui.kpi_row("loaded_kpis", [
            dict(label="Purchases", value=f"{len(spend):,}",
                 help=f"{len(tx) - len(spend)} card payment or transfer row(s) not counted."
                 if len(tx) != len(spend) else None),
            dict(label="Total spent", value=f"${spend['amount'].sum():,.2f}",
                 help="Excludes card payments and transfers, same as Spending breakdown."),
            dict(label="Date range", value=f"{tx['date'].min():%b %Y} to {tx['date'].max():%b %Y}",
                 help=f"{tx['date'].min():%b %d, %Y} to {tx['date'].max():%b %d, %Y}"),
        ])
        st.caption(f"Source: {st.session_state.get('source_name', 'unknown')}")
        with st.container(horizontal=True, key="loaded_actions"):
            st.page_link("app_pages/spending.py", label="See spending breakdown", icon=":material/arrow_forward:")
            if st.button("Clear data", icon=":material/delete:", key="clear_btn"):
                clear_transactions()
                st.rerun()

TUTORIAL = Path(__file__).resolve().parent.parent / "assets" / "tutorial.mp4"
if tx is None and TUTORIAL.exists():
    with ui.section("landing_preview", "How to use it, in about a minute"):
        st.video(str(TUTORIAL), autoplay=True, muted=True, loop=True)
        st.caption("Six steps on a fictional statement: upload a CSV and check the columns, then Spending, "
                   "the Shadow portfolio, the Roth (with your wants spending redirected) and Proof.")
