"""Expected values are worked by hand / Excel, not by calling the code under test."""

import pytest

from core import tvm


def test_fv_lump_hand():
    # 1000 * 1.05^10 = 1628.894627
    assert tvm.fv_lump(1000, 0.05, 10) == pytest.approx(1628.894627, abs=1e-6)


def test_fv_annuity_ordinary_hand():
    # 100 * (1.01^12 - 1) / 0.01 = 1268.250301 (Excel FV(1%,12,-100))
    assert tvm.fv_annuity(100, 0.01, 12) == pytest.approx(1268.250301, abs=1e-6)


def test_fv_annuity_due_hand():
    # due = ordinary * 1.01 = 1280.932804 (Excel FV(1%,12,-100,0,1))
    assert tvm.fv_annuity(100, 0.01, 12, due=True) == pytest.approx(1280.932804, abs=1e-6)


def test_fv_annuity_zero_rate():
    assert tvm.fv_annuity(100, 0.0, 12) == 1200


def test_periodic_rates():
    assert tvm.periodic_rate(0.12, 12, "apr") == pytest.approx(0.01)
    # (1.12)^(1/12) - 1 = 0.009488793
    assert tvm.periodic_rate(0.12, 12, "effective") == pytest.approx(0.009488793, abs=1e-9)


def test_roth_matches_excel_fv_uncapped():
    # Age 21 -> 65, $200/mo, 7% APR monthly: Excel FV(0.07/12, 528, -200) = 705,070.79
    proj = tvm.roth_projection(21, 65, 200, 0.07, enforce_limit=False)
    assert proj.iloc[-1]["balance"] == pytest.approx(705_070.79, abs=0.01)
    assert proj.iloc[-1]["total_contributed"] == pytest.approx(200 * 528)
    assert len(proj) == 44 and proj.iloc[-1]["age"] == 65


def test_roth_with_starting_balance_and_due():
    proj = tvm.roth_projection(30, 40, 300, 0.06, starting_balance=5000, due=True, enforce_limit=False)
    r, n = 0.005, 120
    expected = tvm.fv_lump(5000, r, n) + tvm.fv_annuity(300, r, n, due=True)
    assert proj.iloc[-1]["balance"] == pytest.approx(expected, rel=1e-10)
    assert proj.iloc[-1]["growth"] == pytest.approx(expected - 5000 - 300 * n)


def test_roth_cap_and_catchup():
    # $1,000/mo is over the limit: capped at 7500/12 = 625 before 50, 8600/12 after
    proj = tvm.roth_projection(48, 52, 1000, 0.0)
    assert list(proj["contributed_this_year"]) == pytest.approx([7500, 7500, 8600, 8600])
    assert proj.iloc[-1]["balance"] == pytest.approx(32200)


def test_closed_form_matches_simulation_across_catchup():
    # 45 -> 55 at $700/mo, 7% APR: $625/mo cap for ages 45-49, $700 (< 8600/12) for 50-54
    pmts = tvm.monthly_payments_by_age(45, 55, 700)
    assert pmts == pytest.approx([625] * 5 + [700] * 5)
    r = 0.07 / 12
    fv, segs = tvm.fv_segments(0, pmts, r)
    # hand form: FVA(625, 60) grown 60 more months + FVA(700, 60)
    hand = tvm.fv_annuity(625, r, 60) * (1 + r) ** 60 + tvm.fv_annuity(700, r, 60)
    assert fv == pytest.approx(hand, rel=1e-12)
    assert segs == [(625, 60, 60), (700, 60, 0)]
    sim = tvm.roth_projection(45, 55, 700, 0.07).iloc[-1]["balance"]
    assert fv == pytest.approx(sim, rel=1e-10)


def test_roth_bad_ages():
    with pytest.raises(ValueError):
        tvm.roth_projection(65, 65, 100, 0.07)


def test_tbill_discount_to_effective_annual_hand():
    from core.prices import tbill_effective_annual
    # d = 4.143%: price = 1 - 0.04143*91/360 = 0.98952725; HPR = 1/price - 1 = 0.0105836;
    # EAR = 1.0105836^(365/91) - 1 = 0.043130
    assert tbill_effective_annual(0.04143) == pytest.approx(0.043130, abs=2e-6)
    assert tbill_effective_annual(0.0) == 0.0
