"""Percent of wants vs exact dollars per month: what buys the shadow fund."""
import pandas as pd
import pytest

from core.invest import monthly_buys, scale_purchases


def _spend():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-05-03", "2026-05-20", "2026-07-14"]),
        "description": ["Cafe", "Shoes", "Movie"],
        "amount": [10.00, 80.00, 15.50],
    })


def test_percent_scales_each_purchase_on_its_own_date():
    out = scale_purchases(_spend(), 0.25)
    assert list(out["amount"]) == [2.50, 20.00, 3.875]
    assert list(out["date"]) == list(_spend()["date"])


def test_full_share_is_the_original_spending():
    pd.testing.assert_frame_equal(scale_purchases(_spend(), 1.0), _spend())


@pytest.mark.parametrize("share", [0.0, -0.1, 1.01])
def test_bad_share_rejected(share):
    with pytest.raises(ValueError):
        scale_purchases(_spend(), share)


def test_dollars_buy_on_the_first_of_every_month_spanned():
    # May to July is three months, June included even with no spending in it
    out = monthly_buys(_spend(), 200)
    assert list(out["date"]) == list(pd.to_datetime(["2026-05-01", "2026-06-01", "2026-07-01"]))
    assert list(out["amount"]) == [200.0, 200.0, 200.0]
    assert out["amount"].sum() == 600


def test_dollars_must_be_positive():
    with pytest.raises(ValueError):
        monthly_buys(_spend(), 0)
