import altair as alt
import streamlit as st

from core import edits, ui
from core.categorize import ALL_CATEGORIES, NON_SPEND
from core.state import (get_transactions, require_transactions, set_transactions, set_wants_map,
                        spending_only, wants_map)

ui.page_header(
    "Spending breakdown",
    lede="Totals include only purchases unless you turn on transfers. Rename or split categories, and "
         "ignore one-off purchases (like a gift for family), at the bottom of this page.",
)
tx = edits.ensure_columns(require_transactions())
SOURCE = st.session_state.get("source_name", "edited")

include_transfers = st.toggle(
    "Include transfers and card payments", value=False, key="include_transfers",
    help="Off by default: paying a card bill is not new spending, so counting it double counts.",
)
df = spending_only(tx, include_transfers)
if df.empty:
    st.warning("Nothing left after excluding transfers and ignored purchases.")
    st.stop()
n_ignored = int(tx["ignored"].sum())
if n_ignored:
    st.caption(f":material/visibility_off: {n_ignored} ignored purchase(s), "
               f"\\${tx.loc[tx['ignored'], 'amount'].sum():,.2f}, left out of every total and page. "
               "Untick them under All transactions to count them again.")

months = max(df["date"].dt.to_period("M").nunique(), 1)
total = df["amount"].sum()
disc = df.loc[df["discretionary"], "amount"].sum()

ui.kpi_row("spend_kpis", [
    dict(label="Total spent", value=f"${total:,.2f}"),
    dict(label="Per month (avg)", value=f"${total / months:,.2f}",
         help=f"Over {months} calendar month(s) with spending."),
    dict(label="Discretionary", value=f"${disc:,.2f}", help="Wants: " + (", ".join(edits.want_categories(df)) or "none")),
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
        column_order=["description", "spent", "category", "visits"],
        key="top_table",
    )
    with st.container(key="swipe_hint_merchants"):
        st.caption(":material/swipe: Swipe the table sideways for more columns.")



# --- edits: each runs in a button callback, so it lands before the page redraws --------------
def _apply(new_tx, new_map=None, note=None):
    set_transactions(new_tx, SOURCE)
    if new_map is not None:
        set_wants_map(new_map)
    st.session_state["_cat_note"] = note


def _split():
    ss = st.session_state
    try:
        out, m = edits.split_category(edits.ensure_columns(get_transactions()), ss["split_source"], ss.get("split_merchants") or [],
                                      ss.get("split_name", ""), ss["split_want"], wants_map())
    except ValueError as exc:
        ss["_cat_error"] = str(exc)
        return
    moved = len(ss["split_merchants"])
    _apply(out, m, f"Moved {moved} merchant(s) from {ss['split_source']} into {edits.clean_name(ss['split_name'])}.")
    ss["split_merchants"], ss["split_name"] = [], ""  # clear the form for the next split


def _rename():
    ss = st.session_state
    try:
        out, m = edits.rename_category(edits.ensure_columns(get_transactions()), ss["rename_old"], ss.get("rename_new", ""), wants_map())
    except ValueError as exc:
        ss["_cat_error"] = str(exc)
        return
    _apply(out, m, f"Renamed {ss['rename_old']} to {edits.clean_name(ss['rename_new'])}.")
    ss["rename_new"] = ""


editable = [c for c in edits.ordered_categories(spending_only(tx)) if c not in NON_SPEND]
with ui.section("category_editor", "Your categories"):
    if msg := st.session_state.pop("_cat_error", None):
        st.error(msg)
    if msg := st.session_state.pop("_cat_note", None):
        st.success(msg)
    split_tab, rename_tab = st.tabs(["Split a category", "Rename a category"])
    with split_tab:
        s1, s2 = st.columns([1, 2])
        default_src = editable.index("Shopping") if "Shopping" in editable else 0
        source = s1.selectbox("Category to split", editable, index=default_src, key="split_source")
        merchants = sorted(tx.loc[tx["category"] == source, "description"].unique())
        s2.multiselect("Merchants to move", merchants, key="split_merchants",
                       placeholder="e.g. Nike, Zara")
        s3, s4 = st.columns([1, 2])
        s3.text_input("New category name", max_chars=edits.MAX_NAME, key="split_name",
                      placeholder="e.g. Clothing")
        if st.session_state.get("_split_src_seen") != source:  # default the flag to the source's
            st.session_state["_split_src_seen"] = source
            st.session_state["split_want"] = edits.is_want(source, wants_map())
        s4.toggle("It's a want", key="split_want",
                  help="Wants are what the Shadow portfolio invests and the Roth redirects. "
                       "Needs (rent, groceries, gas) stay out.")
        st.button("Split", icon=":material/call_split:", key="split_btn", on_click=_split)
    with rename_tab:
        r1, r2 = st.columns([1, 2])
        r1.selectbox("Category", editable, key="rename_old")
        r2.text_input("New name", max_chars=edits.MAX_NAME, key="rename_new",
                      help="Renaming onto a category that already exists merges the two.")
        st.button("Rename", icon=":material/edit:", key="rename_btn", on_click=_rename)

options = list(dict.fromkeys(ALL_CATEGORIES + edits.ordered_categories(tx, list(wants_map()))))
with st.expander("All transactions (change a category, or ignore a purchase)", key="all_tx"):
    edited = st.data_editor(
        tx[["ignored", "date", "description", "amount", "category"]],
        hide_index=True,
        disabled=["date", "description", "amount"],
        column_config={
            "ignored": st.column_config.CheckboxColumn(
                "Ignore", help="Tick to leave a purchase out of every total, like a gift for family."),
            "date": st.column_config.DateColumn("Date"),
            "description": "Merchant",
            "amount": st.column_config.NumberColumn("Amount", format="dollar"),
            "category": st.column_config.SelectboxColumn("Category", options=options, required=True),
        },
        key="tx_editor",
    )
    cats_changed = not edited["category"].equals(tx["category"])
    ignored_changed = not edited["ignored"].astype(bool).equals(tx["ignored"].astype(bool))
    if cats_changed or ignored_changed:
        updated = tx
        if cats_changed:
            updated = edits.recategorize(updated, edited["category"], wants_map())
        if ignored_changed:
            updated = edits.set_ignored(updated, edited["ignored"])
        set_transactions(updated, SOURCE)
        st.rerun()
