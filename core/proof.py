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

from core import montecarlo, tvm
from core.portfolios import build_portfolio
from core.shadow import build_shadow

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

def run_checks(tx_all: pd.DataFrame, spend: pd.DataFrame, voo: pd.Series, sample_path=None,
               bnd: pd.Series | None = None, disc_monthly: float | None = None) -> list[Check]:
    """tx_all = every normalized row (transfers included); spend = spending only. The raw-CSV
    spending check runs only for the sample (an upload's raw file isn't kept); the 60/40 check
    runs when BND prices are given; the redirected-spending Roth check runs when the data has
    discretionary spending (disc_monthly = its monthly average)."""
    checks: list[Check] = []

    if sample_path is not None:
        checks.append(Check(
            "Spending: all purchase rows vs the raw CSV", float(tx_all["amount"].sum()),
            raw_sample_spend_total(sample_path), 0.005,
            "Sum of every negative Amount in the sample file, read line by line with Python's csv "
            "module (before transfers are excluded)."))
    voo = voo.dropna().sort_index()
    shadow = build_shadow(spend, voo)
    brute = brute_force_shadow(list(spend["date"]), list(spend["amount"]), list(voo.index),
                               list(voo.to_numpy(dtype=float)))
    checks.append(Check("Shadow: VOO value vs a brute-force loop", shadow.value, brute, 0.005,
                        "Plain Python loop: each purchase buys at the first close on or after its date."))

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
    if disc_monthly:
        app_redirect = float(tvm.roth_projection(d["current_age"], d["retirement_age"], disc_monthly, d["rate"],
                                                 enforce_limit=False).iloc[-1]["balance"])
        checks.append(Check("Roth: redirected discretionary spending vs the annuity formula", app_redirect,
                            disc_monthly * ((1 + r) ** n - 1) / r, 0.005,
                            f"Your discretionary average (${disc_monthly:,.2f}/month) put into the Roth from 21 "
                            f"to 65 at 7% APR, closed form typed out here. Uncapped, so it matches the Roth "
                            f"page only while that amount is under the IRA limit (${tvm.IRA_LIMIT_2026 / 12:,.2f}/month)."))

    mc = montecarlo.simulate_roth(d["current_age"], d["retirement_age"], d["monthly"], method="normal",
                                  annual_mean=d["rate"], annual_vol=0.15, n_sims=5000, seed=0,
                                  enforce_limit=False)
    se = float(np.std(mc["final"], ddof=1) / np.sqrt(mc["n_sims"]))
    checks.append(Check("Monte Carlo: mean of 5,000 runs vs closed form", mc["mean_final"], app_fv, 3 * se,
                        f"Same average return, so the mean should land within 3 standard errors "
                        f"(3 x ${se:,.0f}) of the formula."))
    return checks


def _fmt_value(v: float, unit: str) -> str:
    if unit == "$":
        return f"${v:,.2f}"
    if unit == "%":
        return f"{v:.4%}"
    return f"{v:.6f}"


def _fmt_diff(d: float, unit: str) -> str:
    """Differences a person can read: dollars to the cent, otherwise 6 decimals; a pure
    floating-point speck (well under the display precision) shows as an exact zero."""
    if unit == "$":
        return "$0.00" if abs(d) < 0.005 else f"{'-' if d < 0 else '+'}${abs(d):,.2f}"
    if unit == "%":
        return "0" if abs(d) < 5e-9 else f"{d * 100:+.4f} pts"
    return "0" if abs(d) < 5e-7 else f"{d:+.6f}"


def checks_frame(checks: list[Check]) -> pd.DataFrame:
    """The table on the Proof page. The method for each check is listed separately (how_list)."""
    return pd.DataFrame([{
        "Result": "✓ Pass" if c.passed else "✗ Fail", "Check": c.name,
        "App": _fmt_value(c.app, c.unit), "Independent": _fmt_value(c.independent, c.unit),
        "Difference": _fmt_diff(c.diff, c.unit),
    } for c in checks])


def how_list(checks: list[Check]) -> str:
    """Markdown list: how each check is computed. Dollar signs escaped for Streamlit markdown."""
    return "\n".join(f"{i}. **{c.name}.** {c.how.replace('$', chr(92) + '$')}" for i, c in enumerate(checks, 1))


# ---------- Excel workbook with live formulas ----------

def build_workbook(spend: pd.DataFrame, voo: pd.Series, app: dict) -> bytes:
    """Return .xlsx bytes. Every recomputed cell is an Excel formula; app values sit beside them
    with a difference cell, so a grader can audit the math in Excel. `app` holds the app's numbers:
    shadow_value, roth_fv. Built in memory, never saved to disk."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

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

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
