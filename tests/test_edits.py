"""Ignore rows, rename and split categories: hand-built frames, expected values by hand."""
import pandas as pd
import pytest

from core import edits
from core.state import spending_only


def _tx():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05"]),
        "description": ["NIKE", "TARGET", "TARGET", "KROGER", "CARD PAYMENT"],
        "amount": [50.0, 20.0, 30.0, 40.0, 500.0],
        "category": ["Shopping", "Shopping", "Shopping", "Groceries", "Transfers & Payments"],
        "discretionary": [True, True, True, False, False],
    })


def test_ignored_rows_leave_every_total():
    tx = edits.set_ignored(_tx(), pd.Series([True, False, False, False, False]))
    assert spending_only(tx)["amount"].sum() == 90.0          # 20 + 30 + 40, no Nike, no payment
    assert spending_only(tx, include_transfers=True)["amount"].sum() == 590.0
    assert spending_only(edits.ensure_columns(_tx()))["amount"].sum() == 140.0


def test_split_moves_only_the_picked_merchants():
    out, m = edits.split_category(_tx(), "Shopping", ["TARGET"], "Home", False, {})
    assert list(out["category"]) == ["Shopping", "Home", "Home", "Groceries", "Transfers & Payments"]
    assert list(out["discretionary"]) == [True, False, False, False, False]   # Home marked a need
    assert m == {"Home": False}
    assert edits.want_categories(out) == ["Shopping"]


def test_split_into_a_want_counts_as_wants():
    out, m = edits.split_category(_tx(), "Shopping", ["NIKE"], "  Clothing ", True, {})
    assert m == {"Clothing": True}
    assert out.loc[out["discretionary"], "amount"].sum() == 100.0            # unchanged total of wants
    assert edits.want_categories(out) == ["Shopping", "Clothing"]             # built-ins first


@pytest.mark.parametrize("name, merchants, msg", [
    ("", ["NIKE"], "Type a category name"),
    ("shopping", ["NIKE"], "already exists"),
    ("Transfers & Payments", ["NIKE"], "reserved"),
    ("x" * 31, ["NIKE"], "30 characters"),
    ("Clothing", [], "at least one merchant"),
    ("Clothing", ["KROGER"], "None of those merchants"),
])
def test_split_rejects_bad_input(name, merchants, msg):
    with pytest.raises(ValueError, match=msg):
        edits.split_category(_tx(), "Shopping", merchants, name, True, {})


def test_rename_keeps_the_want_flag():
    out, m = edits.rename_category(_tx(), "Shopping", "Retail", {})
    assert set(out["category"]) == {"Retail", "Groceries", "Transfers & Payments"}
    assert m == {"Retail": True}
    assert out.loc[out["category"] == "Retail", "discretionary"].all()


def test_rename_onto_existing_merges_and_takes_its_flag():
    out, m = edits.rename_category(_tx(), "Shopping", "Groceries", {})
    assert (out["category"] == "Groceries").sum() == 4
    assert not out["discretionary"].any()
    assert m == {}


def test_rename_guards():
    with pytest.raises(ValueError, match="can't be renamed"):
        edits.rename_category(_tx(), "Transfers & Payments", "Bills", {})
    with pytest.raises(ValueError, match="same name"):
        edits.rename_category(_tx(), "Shopping", "Shopping", {})


def test_recategorize_uses_custom_flags():
    out = edits.recategorize(_tx(), pd.Series(["Clothing", "Home", "Shopping", "Groceries",
                                               "Transfers & Payments"]), {"Clothing": True, "Home": False})
    assert list(out["discretionary"]) == [True, False, True, False, False]
    assert edits.ordered_categories(out) == ["Transfers & Payments", "Groceries", "Shopping", "Clothing", "Home"]
