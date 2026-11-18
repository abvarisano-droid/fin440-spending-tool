"""core/proof.py: the independent recomputes by hand, every live check on synthetic data, and
the workbook's formulas (no network)."""

import io

import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from core import proof
from core.state import SAMPLE_CSV


def _prices(seed, n=200, drift=0.0004, vol=0.01):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2026-01-02", periods=n)
    return pd.Series(100 * np.cumprod(1 + rng.normal(drift, vol, n)), index=idx)


def _spend():
    dates = pd.to_datetime(["2026-01-03", "2026-02-10", "2026-03-15", "2026-05-01", "2026-06-20"])
    return pd.DataFrame({"date": dates, "description": list("abcde"),
                         "amount": [10.0, 25.5, 40.0, 7.25, 100.0], "category": "Dining"})


def test_brute_force_shadow_hand():
    # buy 100 at 50 (2 shares) on day 1, 30 at 60 (0.5 share) on day 3 (Saturday rolls forward); last 80
    dates = pd.to_datetime(["2026-01-01", "2026-01-03"])
    px_dates = list(pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"]))
    assert proof.brute_force_shadow(dates, [100, 30], px_dates, [50, 55, 60]) == pytest.approx(2.5 * 60)


def test_fv_loop_matches_excel_figure():
    assert proof.fv_by_loop(200, 0.07, 528) == pytest.approx(proof.ROTH_EXCEL_FV, abs=0.005)


def test_raw_sample_total():
    assert proof.raw_sample_spend_total(SAMPLE_CSV) == pytest.approx(6963.81)


def test_every_check_passes_on_synthetic_data():
    spend = _spend()
    checks = proof.run_checks(spend, spend, _prices(1), _prices(2), 0.04)
    assert len(checks) == 10
    assert all(c.passed for c in checks), [(c.name, c.app, c.independent) for c in checks if not c.passed]


def test_a_wrong_number_fails():
    c = proof.Check("x", 100.0, 100.02, 0.005, "")
    assert not c.passed


def test_workbook_has_live_formulas():
    spend = _spend()
    app = dict(shadow_value=1.0, beta=1.0, vol=0.1, sharpe=0.5, rf_effective=0.043, roth_fv=705_070.79)
    wb = load_workbook(io.BytesIO(proof.build_workbook(spend, _prices(1), _prices(2), 0.0414, app)))
    assert wb.sheetnames == ["Start here", "Roth", "Shadow", "Risk"]
    assert wb["Roth"]["B7"].value == "=FV(B2/12,B3*12,-B4,-B5,0)"
    sh = wb["Shadow"]
    assert sh["E2"].value == "=B2/D2" and sh["F2"].value == "=E2*$I$1"
    assert sh["I6"].value == "=I5-I4"
    risk = [wb["Risk"].cell(i, 8).value for i in range(2, 9)]
    assert risk[3].startswith("=SLOPE(")
    # Excel 2010+ functions need the _xlfn. prefix in the file, or Excel shows #NAME?
    for f in risk[4:]:
        assert "STDEV.S" not in f.replace("_xlfn.STDEV.S", "")
        assert "VAR.S" not in f.replace("_xlfn.VAR.S", "").replace("_xlfn.COVARIANCE.S", "")
