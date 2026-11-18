import io

import pandas as pd
import pytest

from core import ingest
from core.categorize import categorize, categorize_one
from core.state import SAMPLE_CSV


def _df(text):
    return ingest.read_csv(io.BytesIO(text.encode()))


def test_chase_style_negative_purchases():
    df = _df("Transaction Date,Description,Category,Amount\n"
             "01/05/2026,STARBUCKS,Food,-5.25\n01/06/2026,Payment Thank You,,500.00\n"
             "01/07/2026,TARGET,Shopping,-20.00\n")
    m = ingest.detect_columns(df)
    assert (m.date, m.description, m.amount, m.category) == ("Transaction Date", "Description", "Amount", "Category")
    assert ingest.guess_purchases_negative(df, m) is True
    out = ingest.normalize(df, m, True)
    assert out["amount"].tolist() == [5.25, 20.00]  # payment dropped


def test_amex_style_positive_purchases():
    df = _df("Date,Description,Amount\n01/05/2026,UBER EATS,32.10\n01/06/2026,AMAZON,15.00\n"
             "01/07/2026,REFUND,-15.00\n")
    m = ingest.detect_columns(df)
    assert ingest.guess_purchases_negative(df, m) is False
    assert ingest.normalize(df, m, False)["amount"].tolist() == [32.10, 15.00]


def test_debit_credit_columns_and_money_strings():
    df = _df('Posted Date,Payee,Debit,Credit\n2026-01-05,KROGER,"$1,045.10",\n'
             "2026-01-06,PAYROLL,,2000.00\n")
    m = ingest.detect_columns(df)
    assert (m.debit, m.credit, m.description) == ("Debit", "Credit", "Payee")
    out = ingest.normalize(df, m, False)
    assert out["amount"].tolist() == [1045.10]


def test_to_number_parentheses_negative():
    assert ingest.to_number(pd.Series(["(12.50)", "$3.00", "1,000"])).tolist() == [-12.5, 3.0, 1000.0]


@pytest.mark.parametrize("desc,cat", [
    ("UBER EATS ORDER", "Dining"), ("UBER TRIP", "Transport"), ("STARBUCKS 123", "Coffee"),
    ("AMAZON PRIME*1X", "Subscriptions"), ("AMAZON.COM*MK12", "Shopping"),
    ("Payment Thank You-Mobile", "Transfers & Payments"), ("CURRENT ACCOUNT FEE", "Other"),
])
def test_categorize_rules(desc, cat):
    assert categorize_one(desc) == cat


def test_sample_csv_loads():
    raw = ingest.read_csv(SAMPLE_CSV)
    m = ingest.detect_columns(raw)
    tx = categorize(ingest.normalize(raw, m, ingest.guess_purchases_negative(raw, m)))
    assert len(tx) > 100
    assert (tx["amount"] > 0).all()
    assert "Transfers & Payments" not in set(tx["category"])  # card payments are positive, dropped
