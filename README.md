# Spend Shadow (FIN 440)

Upload a bank or card CSV and see where the money went, what it would be worth if every purchase
had bought an index fund instead, and what redirecting some of it into a Roth IRA could grow to.

```
pip install -r requirements.txt
streamlit run streamlit_app.py
python -m pytest            # math + ingest + headless page tests (tests/test_app.py needs network for Yahoo prices)
```

## Pages
| Page | What it does |
|---|---|
| Upload | Reads any bank CSV, auto-detects date/description/amount (or debit/credit) columns, lets you fix the mapping and the purchase sign. "Use sample data" loads a fictional CSV. |
| Spending breakdown | Totals, monthly average, discretionary share, by-category and by-month charts, top merchants, editable categories. Card payments and transfers are excluded by default. |
| Shadow portfolio | Each purchase buys fractional shares of a ticker (VOO default) at the first trading day's adjusted close on or after the purchase. Shows value now, gain, XIRR and a per-purchase ledger. |
| Shadow: compare | The same purchases in up to 4 portfolios (100% VOO, 60/40 VOO/BND, 100% BND, 100% QQQ): value lines plus a table of value, gain, return and XIRR. |
| Risk & CAPM | Volatility, Sharpe, max drawdown, beta and Jensen's alpha vs SPY, a risk vs return scatter and the security market line. Two windows: your purchase dates (time-weighted unit value) or 5 years of fund history (daily-rebalanced mix). Risk-free is the 13-week T-bill (^IRX). |
| Timing test | Replays your purchases on 1,000 random sets of trading days and ranks your real dates (market efficiency), plus the lump-sum comparison. |
| Roth calculator | Monthly contributions (typed, or a % of your discretionary spending), editable return, APR vs effective rate, end vs start of month, 2026 IRA cap ($7,500 + $1,100 catch-up at 50+). "Show the math" prints the closed-form FV. "With uncertain returns" runs a Monte Carlo (normal or bootstrap from real fund months): percentile fan, median, 5th percentile, odds of a target. |

## Math conventions
- **Spending is gross purchases.** Refunds, deposits and other money coming in are dropped, not
  netted against a category, because a bank CSV can't reliably tell a refund from income. In the
  sample that leaves out one $23.40 Amazon return. Card payments and transfers are categorized
  but excluded from totals on every page.
- **Discretionary** = Dining, Coffee, Entertainment, Shopping, Subscriptions, Travel. Transport and
  Gas count as needs.
- **Roth:** month-by-month simulation; matches `FV = PV(1+r)^n + PMT((1+r)^n - 1)/r` (times `(1+r)` if due). APR mode uses r = rate/12, the same as Excel `FV(rate/12, n, -pmt)`. When the IRA cap changes the payment (the age-50 catch-up), "Show the math" splits it into segments, each annuity grown to retirement, and the total equals the simulation. A real return means outputs are in today's dollars.
- **Shadow:** dividend-adjusted closes (dividends reinvested), no fees or taxes. Purchases after the latest price are skipped and counted. XIRR is shown only for spans of a week or more.
- **Portfolios:** each purchase is split by fixed weights and held (no rebalancing). All slices buy on the first day every fund in the mix traded.
- **Risk:** simple daily returns; vol = sample std x sqrt(252); Sharpe on excess returns over the T-bill; beta and alpha by OLS on excess returns (alpha x 252, arithmetic). The purchase window uses a time-weighted unit value (NAV method) so deposits never count as returns. T-bill: bank discount yield to effective annual, `(1/(1 - d*91/360))^(365/91) - 1`. "Above SML" = realized geometric return minus the CAPM expected return.
- **Timing test:** each shuffle moves every purchase to a uniform random trading day between the first and last real buy (seed 0). Percentile = share of shuffles beaten, ties count half.
- **Monte Carlo:** the normal method uses the same average monthly rate as the fixed-return chart, so the mean of the runs should match the closed-form FV (a check shown on the page); the median is lower because of volatility drag. Bootstrap returns are nominal.

Deploying: see [DEPLOY.md](DEPLOY.md) (Streamlit Community Cloud, Python 3.12, pinned requirements).

## Privacy
Uploads live only in `st.session_state` for the browser session. Nothing is written to disk or
logged. The only outbound request carrying anything derived from your data is the ticker and
start date (your earliest purchase date) sent to Yahoo Finance. Streamlit's own usage telemetry
is turned off in `.streamlit/config.toml` (`gatherUsageStats = false`). The browser also loads the app's fonts from Google Fonts; that request carries no data from your file. `data/` is
gitignored for any real CSVs you keep locally. Never commit real statements.

## Code layout
- `streamlit_app.py`: navigation entrypoint. `app_pages/`: one file per page (UI only).
- `core/`: pure logic (`ingest`, `categorize`, `shadow`, `tvm`, `portfolios`, `risk`, `timing`, `montecarlo`, `lab` for page glue) plus `prices` (yfinance + cache) and `state`.
- `tests/`: hand-checked TVM and portfolio values, ingest cases, headless page smoke tests.

## Design
Grok (designer) owns the look: `DESIGN.md`, `.streamlit/config.toml`, `styles.css` and
`core/ui.py`. Roles, file ownership and the phase workflow are in [AGENTS.md](AGENTS.md).
- `core/ui.py` holds every presentation helper: `section(key, title)` (card),
  `kpi_row(key, items)` (metrics row), `chart(altair_chart)` (shared chart styling). Pages only
  call these.
- `core/state.load_styles()` injects `styles.css` automatically once it exists.
- Every block is keyed, so CSS can target `.st-key-<key>`: `upload_source`, `column_mapper`,
  `loaded_summary`, `loaded_kpis`, `loaded_actions`, `spend_kpis`, `chart_by_category`, `table_by_category`,
  `chart_by_month`, `top_merchants`, `shadow_controls`, `shadow_kpis`, `chart_shadow`,
  `shadow_compare`, `roth_inputs`, `roth_kpis`, `chart_roth`, `roth_mc_controls`, `chart_roth_fan`,
  `roth_mc_kpis`, `risk_kpis`, `chart_risk_return`, `chart_sml`, `risk_table`, `risk_explainer`, `timing_kpis`,
  `chart_timing_hist`, `timing_explainer`. Phase 7 chart helpers: `chart_fan`, `chart_histogram`,
  `chart_risk_return`, `chart_sml`.

## Agent setup (one terminal tab each, all in this folder)
| Tab | Command | Role |
|---|---|---|
| 1 | `grok` | Designer. Reads GROK.md, then AGENTS.md. |
| 2 | `claude --add-dir ..\second-brain` | Builder. CLAUDE.md imports AGENTS.md. |
| 3 | `claude` (new session, first prompt: "You're the auditor") | Auditor, read-only. Say "audit phase N". |

Agents pass work and requests through [HANDOFF.md](HANDOFF.md).
