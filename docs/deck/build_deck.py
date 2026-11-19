"""Build the FIN 440 deck: charts from the app's own engines (one price snapshot) + a .pptx."""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
REPO = r"C:\Users\jvari\code\fin440-spend-shadow"
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from core import categorize, ingest, lab, montecarlo, risk, tvm
from core.portfolios import PRESETS
from core.prices import fetch_history, fetch_many, fetch_risk_free
from core.state import SAMPLE_CSV, spending_only
from core.timing import timing_test

# ---- tokens (DESIGN.md) ----
PAPER, INK, MUTED, GRID = "#F4EFE6", "#1C1915", "#6E675C", "#E6DDD0"
PINE, ORANGE, BLUE, GREEN, SAGE, TINT, BRICK = "#1E4A3A", "#B45309", "#2C4A6E", "#1E6B45", "#A8B894", "#EDE6D9", "#A33B32"
PCOL = {"100% VOO": ORANGE, "60/40 VOO/BND": BLUE, "100% BND": MUTED, "100% QQQ": PINE, "SPY (market)": INK}
plt.rcParams.update({"font.family": "Arial", "axes.facecolor": PAPER, "figure.facecolor": PAPER,
                     "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 13})

raw = ingest.read_csv(SAMPLE_CSV); m = ingest.detect_columns(raw)
tx = categorize.categorize(ingest.normalize(raw, m, ingest.guess_purchases_negative(raw, m)))
s = spending_only(tx)
months = s["date"].dt.to_period("M").nunique()
N = {}
N["total"] = s["amount"].sum(); N["monthly"] = N["total"] / months
N["disc"] = s.loc[s["discretionary"], "amount"].sum()
rf = fetch_risk_free(); N["rf"] = rf["effective_annual"]; N["rf_d"] = rf["discount_yield"]; N["asof"] = f"{rf['as_of']:%b %d, %Y}"
tick = lab.tickers_for(list(PRESETS), ("SPY",))
p = fetch_many(tick, s["date"].min())
ports = lab.preset_portfolios(s, p, list(PRESETS))
N["ports"] = {n: (r.value, r.simple_return) for n, r in ports.items()}

def money(ax):
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))

# 1 spending by category
cat = s.groupby("category")["amount"].sum().sort_values()
fig, ax = plt.subplots(figsize=(7, 4.6))
ax.barh(cat.index, cat.values, color=[ORANGE if c in categorize.DISCRETIONARY else BLUE for c in cat.index])
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
ax.grid(axis="y", visible=False)
ax.set_title("Sample spending by category (orange = wants)", color=INK, loc="left", fontsize=14)
fig.tight_layout(); fig.savefig(f"{OUT}/spending.png", dpi=200); plt.close(fig)

# 2 compare
fig, ax = plt.subplots(figsize=(11, 4.6))
first = next(iter(ports.values())).timeline
ax.step(first["date"], first["invested"], where="post", color=MUTED, lw=2, ls="--", label="Spent (cumulative)")
for n, r in ports.items():
    ax.step(r.timeline["date"], r.timeline["value"], where="post", color=PCOL[n], lw=2.2, label=n)
money(ax); ax.legend(frameon=False, ncol=5, loc="upper left", fontsize=11)
fig.tight_layout(); fig.savefig(f"{OUT}/compare.png", dpi=200); plt.close(fig)

# 3 SML: 5y vs purchase window
h = {t: fetch_history(t, 5) for t in tick}
ser5 = {n: lab.constant_mix_index(h, PRESETS[n]) for n in PRESETS}
ser5["SPY (market)"] = h["SPY"].loc[ser5["100% VOO"].index[0]:]
t5 = lab.risk_table(ser5, h["SPY"], N["rf"]); mk5 = lab.market_annual_return(h["SPY"], ser5["100% VOO"].index)
serw = {n: r.unit_value for n, r in ports.items()}
serw["SPY (market)"] = p["SPY"].loc[serw["100% VOO"].index[0]:]
tw = lab.risk_table(serw, p["SPY"], N["rf"]); mkw = lab.market_annual_return(p["SPY"], serw["100% VOO"].index)
N["t5"] = t5.set_index("name")[["ann_return", "ann_vol", "sharpe", "max_drawdown", "beta", "alpha_annual"]].round(4).to_dict("index")
N["mk5"], N["mkw"] = mk5, mkw
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=False)
for ax, tbl, mk, title in ((axes[0], t5, mk5, "Last 5 years"), (axes[1], tw, mkw, "Your 6-month purchase window")):
    b = np.array([0, 1.7]); ax.plot(b, N["rf"] + b * (mk - N["rf"]), color=PINE, lw=2.5, label="SML: rf + beta(Rm - rf)")
    for _, r in tbl.iterrows():
        ax.scatter(r["beta"], r["ann_return"], s=110, color=PCOL[r["name"]], zorder=3)
        off = {"100% VOO": (-62, 10), "SPY (market)": (10, -16)}.get(r["name"], (6, 6))
        ax.annotate(r["name"].replace(" (market)", ""), (r["beta"], r["ann_return"]), textcoords="offset points",
                    xytext=off, fontsize=10, color=INK)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Beta vs SPY"); ax.set_title(title, color=INK, loc="left", fontsize=14)
axes[0].set_ylabel("Annual return")
fig.tight_layout(); fig.savefig(f"{OUT}/sml.png", dpi=200); plt.close(fig)

# 4 timing
tt = timing_test(s, p["VOO"])
N["tt"] = {k: tt[k] for k in ("actual_value", "median_shuffled", "percentile", "p_value_two_sided", "lump_sum_value")}
N["tt"]["lo"], N["tt"]["hi"] = float(tt["shuffled_values"].min()), float(tt["shuffled_values"].max())
fig, ax = plt.subplots(figsize=(11, 4.4))
ax.hist(tt["shuffled_values"], bins=40, color="#C9D0B0")
ax.axvline(tt["actual_value"], color=PINE, lw=3, label=f"Your dates: ${tt['actual_value']:,.0f} ({tt['percentile']:.0%} beaten)")
ax.axvline(tt["median_shuffled"], color=MUTED, lw=2, ls="--", label=f"Median random: ${tt['median_shuffled']:,.0f}")
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
ax.set_ylabel("Shuffles"); ax.legend(frameon=False, loc="upper left"); ax.grid(axis="x", visible=False)
fig.tight_layout(); fig.savefig(f"{OUT}/timing.png", dpi=200); plt.close(fig)

# 5 roth fan
mc = montecarlo.simulate_roth(21, 65, 200, method="normal", annual_mean=0.07, annual_vol=0.15, n_sims=5000, seed=0)
proj = tvm.roth_projection(21, 65, 200, 0.07)
pc = mc["percentiles"]
N["roth"] = {"fv": float(proj.iloc[-1]["balance"]), "put_in": float(proj.iloc[-1]["total_contributed"]),
             "p50": float(pc.iloc[-1]["p50"]), "p5": float(pc.iloc[-1]["p5"]), "p95": float(pc.iloc[-1]["p95"]),
             "mean": mc["mean_final"], "odds": montecarlo.prob_reaching(mc["final"], 705_000)}
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.fill_between(pc.index, pc["p5"], pc["p95"], color="#DCCFB8", label="5th to 95th percentile")
ax.fill_between(pc.index, pc["p25"], pc["p75"], color=SAGE, label="25th to 75th")
ax.plot(pc.index, pc["p50"], color=PINE, lw=2.5, label="Median")
ax.plot(proj["age"], proj["balance"], color=ORANGE, lw=2.2, ls="--", label="Fixed 7% calculator")
money(ax); ax.set_xlabel("Age"); ax.legend(frameon=False, loc="upper left")
fig.tight_layout(); fig.savefig(f"{OUT}/fan.png", dpi=200); plt.close(fig)

json.dump(N, open(f"{OUT}/numbers.json", "w"), indent=1, default=float)
print(json.dumps(N, indent=1, default=float))
