import altair as alt
import streamlit as st

from core import ui
from core.categorize import ALL_CATEGORIES, DISCRETIONARY
from core.state import require_transactions, set_transactions, spending_only

st.title("Spending breakdown")
st.caption(":material/school: FIN 440 link (Bodie, Kane & Marcus, 13e): Ch 1 (saving vs. consumption), Ch 12 (behavioral finance: impulse spending, mental accounting).")
st.caption("Totals include only purchases unless you turn on transfers.")
tx = require_transactions()

include_transfers = st.toggle(
    "Include transfers and card payments", value=False, key="include_transfers",
    help="Off by default: paying a card bill is not new spending, so counting it double counts.",
)
df = spending_only(tx, include_transfers)
if df.empty:
    st.warning("Nothing left after excluding transfers.")
    st.stop()

months = max(df["date"].dt.to_period("M").nunique(), 1)
total = df["amount"].sum()
disc = df.loc[df["discretionary"], "amount"].sum()

ui.kpi_row("spend_kpis", [
    dict(label="Total spent", value=f"${total:,.2f}"),
    dict(label="Per month (avg)", value=f"${total / months:,.2f}",
         help=f"Over {months} calendar month(s) with spending."),
    dict(label="Discretionary", value=f"${disc:,.2f}", help="Wants: " + ", ".join(sorted(DISCRETIONARY))),
    dict(label="Discretionary share", value=f"{disc / total:.0%}" if total else "n/a"),
])

by_cat = (
    df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
)
by_cat["share"] = by_cat["amount"] / total

c1, c2 = st.columns([3, 2])
with c1, ui.section("chart_by_category", "By category"):
    ui.chart(
        alt.Chart(by_cat)
        .mark_bar()
        .encode(
            x=alt.X("amount:Q", title="Spent ($)"),
            y=alt.Y("category:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("amount:Q", title="Spent", format="$,.2f"),
                alt.Tooltip("share:Q", title="Share", format=".1%"),
            ],
        ),
    )
with c2, ui.section("table_by_category", "Totals"):
    st.dataframe(
        by_cat.assign(share=by_cat["share"] * 100),  # display only: one decimal everywhere
        hide_index=True,
        column_config={
            "category": "Category",
            "amount": st.column_config.NumberColumn("Spent", format="dollar"),
            "share": st.column_config.NumberColumn("Share", format="%.1f%%"),
        },
        key="cat_table",
    )

monthly = (
    df.assign(month=df["date"].dt.to_period("M").dt.to_timestamp())
    .groupby(["month", "category"], as_index=False)["amount"].sum()
)
with ui.section("chart_by_month", "By month"):
    ui.chart(
        alt.Chart(monthly)
        .mark_bar()
        .encode(
            x=alt.X("yearmonth(month):O", title=None),
            y=alt.Y("sum(amount):Q", title="Spent ($)"),
            color=alt.Color("category:N", title="Category"),
            tooltip=[
                alt.Tooltip("yearmonth(month):O", title="Month"),
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("sum(amount):Q", title="Spent", format="$,.2f"),
            ],
        ),
    )

top = (
    df.groupby("description", as_index=False)
    .agg(spent=("amount", "sum"), visits=("amount", "size"), category=("category", "first"))
    .sort_values("spent", ascending=False)
    .head(10)
)
with ui.section("top_merchants", "Top 10 merchants"):
    st.dataframe(
        top,
        hide_index=True,
        column_config={
            "description": "Merchant",
            "spent": st.column_config.NumberColumn("Spent", format="dollar"),
            "visits": "Visits",
            "category": "Category",
        },
        key="top_table",
    )

with st.expander("All transactions (edit categories here)", key="all_tx"):
    edited = st.data_editor(
        tx[["date", "description", "amount", "category"]],
        hide_index=True,
        disabled=["date", "description", "amount"],
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "amount": st.column_config.NumberColumn("Amount", format="dollar"),
            "category": st.column_config.SelectboxColumn("Category", options=ALL_CATEGORIES, required=True),
        },
        key="tx_editor",
    )
    if not edited["category"].equals(tx["category"]):
        updated = tx.copy()
        updated["category"] = edited["category"].values
        updated["discretionary"] = updated["category"].isin(DISCRETIONARY)
        set_transactions(updated, st.session_state.get("source_name", "edited"))
        st.rerun()
