"""Proof: live independent checks and an Excel cross-check workbook.

Every check compares an app engine's number with a second computation that does NOT call that
engine (a plain loop, numpy, a different engine, or a published Excel figure). Pure functions:
prices and transactions are passed in, nothing is fetched or written to disk here.
"""

from __future__ import annotations

import bisect
import csv
import io
from dataclasses import dataclass

import numpy as np
import pandas as pd

from core import lab, montecarlo, risk, tvm
from core.portfolios import build_portfolio
from core.shadow import build_shadow
from core.timing import timing_test

# Roth defaults and Excel's own answer: =FV(0.07/12, 528, -200) in Excel 365 = 705,070.79
ROTH_DEFAULTS = dict(current_age=21, retirement_age=65, monthly=200.0, rate=0.07)
ROTH_EXCEL_FV = 705_070.79


@dataclass
class Check:
    name: str
    app: float
    independent: float
    tolerance: float
    how: str
    unit: str = "$"  # "$", "x" (ratio) or "%"

    @property
    def diff(self) -> float:
        return self.app - self.independent

    @property
    def passed(self) -> bool:
        return bool(np.isfinite(self.diff) and abs(self.diff) <= self.tolerance)


# ---------- independent recomputes (no app engines inside) ----------

def raw_sample_spend_total(path) -> float:
    """Sum of every negative Amount in a Chase-style CSV, read with the csv module, not pandas."""
    total = 0.0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            amt = float(row["Amount"])
            if amt < 0:
                total += -amt
    return round(total, 2)


def brute_force_shadow(dates, amounts, price_dates, prices) -> float:
    """Loop over purchases: buy at the first trading day on or after each date, value at the last price."""
    pd_list = list(price_dates)
    last = prices[-1]
    total = 0.0
    for d, a in zip(dates, amounts):
        i = bisect.bisect_left(pd_list, d)
        if i < len(pd_list):
            total += a / prices[i] * last
    return total


def fv_by_loop(monthly: float, rate_apr: float, months: int) -> float:
    """End-of-month deposits compounded one month at a time."""
    r, bal = rate_apr / 12, 0.0
    for _ in range(months):
        bal = bal * (1 + r) + monthly
    return bal


# ---------- the live checks ----------

def run_checks(tx_all: pd.DataFrame, spend: pd.DataFrame, voo: pd.Series, spy: pd.Series,
               rf_annual: float, sample_path=None, bnd: pd.Series | None = None) -> list[Check]:
    """tx_all = every normalized row (transfers included); spend = spending only. The raw-CSV
    spending check runs only for the sample (an upload's raw file isn't kept); the 60/40 check
    runs when BND prices are given."""
    checks: list[Check] = []

    if sample_path is not None:
        checks.append(Check(
            "Spending: all purchase rows vs the raw CSV", float(tx_all["amount"].sum()),
            raw_sample_spend_total(sample_path), 0.005,
            "Sum of every negative Amount in the sample file, read line by line with Python's csv "
            "module (before transfers are excluded)."))
    voo = voo.dropna().sort_index()
    spy = spy.dropna().sort_index()
    shadow = build_shadow(spend, voo)
    brute = brute_force_shadow(list(spend["date"]), list(spend["amount"]), list(voo.index),
                               list(voo.to_numpy(dtype=float)))
    checks.append(Check("Shadow: VOO value vs a brute-force loop", shadow.value, brute, 0.005,
                        "Plain Python loop: each purchase buys at the first close on or after its date."))

    port = build_portfolio(spend, {"VOO": voo}, {"VOO": 1.0})  # unit value for the risk checks
    if bnd is not None:
        bnd = bnd.dropna().sort_index()
        both = voo.index.intersection(bnd.index)
        mix = build_portfolio(spend, {"VOO": voo, "BND": bnd}, {"VOO": 0.6, "BND": 0.4})
        dates, amts = list(spend["date"]), spend["amount"].to_numpy(dtype=float)
        brute_mix = sum(brute_force_shadow(dates, list(amts * w), list(both), list(s.loc[both].to_numpy(dtype=float)))
                        for s, w in ((voo, 0.6), (bnd, 0.4)))
        checks.append(Check("Portfolio: 60/40 VOO/BND vs a brute-force loop", mix.value, brute_mix, 0.005,
                            "Plain loop: 60% of each purchase buys VOO and 40% buys BND on the first day "
                            "both traded, valued at the latest closes."))

    tt = timing_test(spend, voo, n_shuffles=50, seed=0)
    checks.append(Check("Timing test 'your dates' vs shadow engine", tt["actual_value"], shadow.value,
                        0.005, "The timing test's unshuffled value is the shadow value."))

    # beta on the purchase window: unit value of 100% VOO is VOO's own price relative
    table = lab.risk_table({"VOO": port.unit_value, "SPY": spy.loc[port.unit_value.index[0]:]}, spy, rf_annual)
    b_app = float(table.iloc[0]["beta"])
    w = pd.concat([voo, spy], axis=1, join="inner").loc[port.unit_value.index[0]:]
    rv, rs = w.iloc[:, 0].pct_change().dropna(), w.iloc[:, 1].pct_change().dropna()
    b_np = float(np.cov(rv, rs, ddof=1)[0, 1] / np.var(rs, ddof=1))
    checks.append(Check("Beta: regression vs cov/var", b_app, b_np, 1e-9,
                        "numpy cov(VOO, SPY) / var(SPY) on daily price returns. Subtracting a constant "
                        "risk-free rate doesn't change the slope.", "x"))
    vol_np = float(np.std(rv, ddof=1) * np.sqrt(252))
    checks.append(Check("Volatility: app vs numpy", float(table.iloc[0]["ann_vol"]), vol_np, 1e-9,
                        "numpy sample std of daily returns x sqrt(252).", "%"))
    rf_d = (1 + rf_annual) ** (1 / 252) - 1
    sharpe_np = float((rv.mean() - rf_d) / np.std(rv, ddof=1) * np.sqrt(252))
    checks.append(Check("Sharpe ratio: app vs a hand formula", float(table.iloc[0]["sharpe"]), sharpe_np, 1e-9,
                        "(average daily return - daily T-bill rate) / std x sqrt(252), in numpy.", "x"))
    d = ROTH_DEFAULTS
    proj = tvm.roth_projection(d["current_age"], d["retirement_age"], d["monthly"], d["rate"],
                               enforce_limit=False)
    n = (d["retirement_age"] - d["current_age"]) * 12
    app_fv = float(proj.iloc[-1]["balance"])
    checks.append(Check("Roth: app vs Excel FV(7%/12, 528, -200)", app_fv, ROTH_EXCEL_FV, 0.005,
                        "Excel's published answer, rounded to the cent."))
    r = d["rate"] / 12
    closed = d["monthly"] * ((1 + r) ** n - 1) / r
    checks.append(Check("Roth: app's month-by-month balance vs the annuity formula", app_fv, closed, 0.005,
                        "Closed form PMT x ((1+r)^n - 1) / r, typed out here, not the app's TVM code."))

    mc = montecarlo.simulate_roth(d["current_age"], d["retirement_age"], d["monthly"], method="normal",
                                  annual_mean=d["rate"], annual_vol=0.15, n_sims=5000, seed=0,
                                  enforce_limit=False)
    se = float(np.std(mc["final"], ddof=1) / np.sqrt(mc["n_sims"]))
    checks.append(Check("Monte Carlo: mean of 5,000 runs vs closed form", mc["mean_final"], app_fv, 3 * se,
                        f"Same average return, so the mean should land within 3 standard errors "
                        f"(3 x ${se:,.0f}) of the formula."))
    return checks


def checks_frame(checks: list[Check]) -> pd.DataFrame:
    def fmt(v, unit):
        if unit == "$":
            return f"${v:,.2f}"
        if unit == "%":
            return f"{v:.6%}"
        return f"{v:.6f}"
    return pd.DataFrame([{
        "Check": c.name, "App": fmt(c.app, c.unit), "Independent": fmt(c.independent, c.unit),
        "Difference": f"{c.diff:+.2e}", "Result": "Pass" if c.passed else "Fail", "How": c.how,
    } for c in checks])


# ---------- Excel workbook with live formulas ----------

def build_workbook(spend: pd.DataFrame, voo: pd.Series, spy: pd.Series, rf_discount: float,
                   app: dict) -> bytes:
    """Return .xlsx bytes. Every recomputed cell is an Excel formula; app values sit beside them
    with a difference cell, so a grader can audit the math in Excel. `app` holds the app's numbers:
    shadow_value, beta, vol, sharpe, rf_effective, roth_fv. Built in memory, never saved to disk."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    # Excel 2010+ functions (STDEV.S, VAR.S, COVARIANCE.S) must carry the _xlfn. prefix in the
    # file, or Excel shows #NAME?. Excel displays them without it.

    bold = Font(bold=True)
    wb = Workbook()

    ws = wb.active
    ws.title = "Start here"
    ws["A1"] = "Spend Shadow: cross-check workbook (FIN 440)"
    ws["A1"].font = Font(bold=True, size=14)
    notes = [
        "Each sheet recomputes an app number with Excel formulas, next to the app's own value.",
        "The Difference cells should all be 0 (or a rounding speck). Change any input to see it flow.",
        "Roth: Excel FV() on the app's default inputs.",
        "Shadow: every purchase buys VOO at the first close on or after it; value at the latest close.",
        "Risk: daily returns, SLOPE() for beta, STDEV.S for volatility, the T-bill conversion, Sharpe.",
        "Prices are Yahoo Finance dividend-adjusted closes as of the download.",
    ]
    for i, t in enumerate(notes, start=3):
        ws.cell(i, 1, t)
    ws.column_dimensions["A"].width = 100

    # Roth
    r = wb.create_sheet("Roth")
    d = ROTH_DEFAULTS
    rows = [("Annual return (APR)", d["rate"]), ("Years", d["retirement_age"] - d["current_age"]),
            ("Monthly contribution", d["monthly"]), ("Starting balance", 0.0)]
    for i, (k, v) in enumerate(rows, start=2):
        r.cell(i, 1, k), r.cell(i, 2, v)
    r["A7"], r["B7"] = "Excel FV", "=FV(B2/12,B3*12,-B4,-B5,0)"
    r["A8"], r["B8"] = "App balance", app["roth_fv"]
    r["A9"], r["B9"] = "Difference", "=B8-B7"
    for c in ("A7", "A8", "A9"):
        r[c].font = bold
    r.column_dimensions["A"].width = 28
    r.column_dimensions["B"].width = 16

    # Shadow
    s = wb.create_sheet("Shadow")
    voo = voo.dropna().sort_index()
    idx = voo.index
    hdr = ["Spent on", "Amount", "Bought on", "VOO close", "Shares", "Worth now"]
    for j, h in enumerate(hdr, start=1):
        s.cell(1, j, h).font = bold
    s["H1"], s["I1"] = "Latest VOO close", float(voo.iloc[-1])
    row = 2
    for dt, amt in zip(spend["date"], spend["amount"]):
        i = idx.searchsorted(dt, side="left")
        if i >= len(idx):
            continue
        s.cell(row, 1, dt.to_pydatetime()).number_format = "yyyy-mm-dd"
        s.cell(row, 2, float(amt))
        s.cell(row, 3, idx[i].to_pydatetime()).number_format = "yyyy-mm-dd"
        s.cell(row, 4, float(voo.iloc[i]))
        s.cell(row, 5, f"=B{row}/D{row}")
        s.cell(row, 6, f"=E{row}*$I$1")
        row += 1
    last = row - 1
    s["H3"], s["I3"] = "Total spent", f"=SUM(B2:B{last})"
    s["H4"], s["I4"] = "Excel value", f"=SUM(F2:F{last})"
    s["H5"], s["I5"] = "App value", app["shadow_value"]
    s["H6"], s["I6"] = "Difference", "=I5-I4"
    for c in ("H3", "H4", "H5", "H6"):
        s[c].font = bold
    s.column_dimensions["H"].width = 18

    # Risk
    k = wb.create_sheet("Risk")
    w = pd.concat([voo.rename("VOO"), spy.dropna().rename("SPY")], axis=1, join="inner")
    w = w.loc[w.index >= idx[idx.searchsorted(spend["date"].min(), side="left")]]
    for j, h in enumerate(["Date", "VOO", "SPY", "VOO return", "SPY return"], start=1):
        k.cell(1, j, h).font = bold
    for i, (dt, rowv) in enumerate(w.iterrows(), start=2):
        k.cell(i, 1, dt.to_pydatetime()).number_format = "yyyy-mm-dd"
        k.cell(i, 2, float(rowv["VOO"]))
        k.cell(i, 3, float(rowv["SPY"]))
        if i > 2:
            k.cell(i, 4, f"=B{i}/B{i - 1}-1")
            k.cell(i, 5, f"=C{i}/C{i - 1}-1")
    end = 1 + len(w)
    rv, rs = f"D3:D{end}", f"E3:E{end}"
    calc = [
        ("T-bill discount yield", rf_discount, None),
        ("T-bill effective annual", "=(1/(1-H2*91/360))^(365/91)-1", app["rf_effective"]),
        ("Daily risk-free", "=(1+H3)^(1/252)-1", None),
        ("Beta (SLOPE)", f"=SLOPE({rv},{rs})", app["beta"]),
        ("Beta (COVARIANCE.S / VAR.S)", f"=_xlfn.COVARIANCE.S({rv},{rs})/_xlfn.VAR.S({rs})", app["beta"]),
        ("Volatility (yearly)", f"=_xlfn.STDEV.S({rv})*SQRT(252)", app["vol"]),
        ("Sharpe ratio", f"=(AVERAGE({rv})-H4)/_xlfn.STDEV.S({rv})*SQRT(252)", app["sharpe"]),
    ]
    k["G1"], k["H1"], k["I1"], k["J1"] = "Measure", "Excel", "App", "Difference"
    for c in ("G1", "H1", "I1", "J1"):
        k[c].font = bold
    for i, (label, formula, app_v) in enumerate(calc, start=2):
        k.cell(i, 7, label)
        k.cell(i, 8, formula)
        if app_v is not None:
            k.cell(i, 9, float(app_v))
            k.cell(i, 10, f"=I{i}-H{i}")
    k.column_dimensions["G"].width = 30

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
