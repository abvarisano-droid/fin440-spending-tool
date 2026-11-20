# Spend Shadow (FIN 440)

**Live:** https://fin440-spending-to-uaoynqbehwjlulmegnfrpf.streamlit.app/

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
| Upload | Shows a narrated tutorial video until data is loaded (`assets/tutorial.mp4`: six steps on the fictional sample, from uploading a CSV to Proof, with an AI voice-over (edge-tts, script in `tools/narration.py`) and subtitles; re-record with `python tools/record_tutorial.py <url>`). Reads any bank CSV, auto-detects date/description/amount (or debit/credit) columns, lets you fix the mapping and the purchase sign. "Use sample data" loads a fictional CSV. |
| Spending breakdown | Totals, monthly average, discretionary share, by-category and by-month charts, top merchants, editable categories. Card payments and transfers are excluded by default. |
| Shadow portfolio | Only discretionary (wants) spending is shadowed: dining, coffee, entertainment, shopping, subscriptions, travel (needs like groceries, gas and bills stay out). Each want buys fractional shares of a ticker (VOO default) at the first trading day's adjusted close on or after the purchase. Shows value now, gain, XIRR and a per-purchase ledger. |
| Shadow: compare | The same purchases in up to 4 portfolios (100% VOO, 60/40 VOO/BND, 100% BND, 100% SCHD): value lines plus a table of value, gain, return and XIRR. One-click fund chips (VOO, SCHD, XLV, QQQ, GLD) set the ticker. |
| Roth calculator | "Fund it from: My spending" (the default with data loaded): pick categories (wants by default); what you spent on them becomes the starting balance (trimmed so it plus 12 monthly payments stays within the $7,500 IRA limit; a warning shows if your edits go over) and the monthly amount is pre-filled with a suggestion by spending level (`core/suggest.py`: under $200/month of wants suggests 50%, $200 to $500 suggests 35%, over $500 suggests 25%, rounded to $25, capped at $625). "Enter my own" types any numbers. Editable return, APR vs effective rate, end vs start of month, 2026 IRA cap ($7,500 + $1,100 catch-up at 50+). "What your spending could become" shows your plan plus 25%, 50% and all of the monthly average redirected into the Roth. "Show the math" prints the closed-form FV. "With uncertain returns" runs a Monte Carlo (normal or bootstrap from real fund months): percentile fan, median, 5th percentile, odds of a target. |
| Proof | 8 live checks on the sample (up to 7 on an upload; 5 if it has no wants spending), each pairing an app number with an independent recompute (raw-CSV re-read, brute-force loops, Excel's FV figure, the annuity formula for the default and the redirected-wants Roth, PV plus annuity for the suggested plan, a second engine for Monte Carlo), pass/fail with both numbers. Downloads an Excel workbook built in memory whose cells are real formulas (FV, shares and value per purchase) next to the app's values. Plus how AI built and audited the app. |

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
- **Risk (engine kept, page removed):** simple daily returns; vol = sample std x sqrt(252); Sharpe on excess returns over the T-bill; beta and alpha by OLS on excess returns (alpha x 252, arithmetic). The purchase window uses a time-weighted unit value (NAV method) so deposits never count as returns. T-bill: bank discount yield to effective annual, `(1/(1 - d*91/360))^(365/91) - 1`. "Above SML" = realized geometric return minus the CAPM expected return.
- **Timing test (engine kept, page removed):** each shuffle moves every purchase to a uniform random trading day between the first and last real buy (seed 0). Percentile = share of shuffles beaten, ties count half.
- **Monte Carlo:** the normal method uses the same average monthly rate as the fixed-return chart, so the mean of the runs should match the closed-form FV (a check shown on the page); the median is lower because of volatility drag. Bootstrap returns are nominal.

Deploying: see [DEPLOY.md](DEPLOY.md) (Streamlit Community Cloud, Python 3.12, pinned requirements).

## Privacy
Uploads live only in `st.session_state` for the browser session. The app never writes them to
disk or logs them (yfinance keeps only a ticker-metadata cache on disk; see DEPLOY.md for the
crash-log caveat). The only outbound request carrying anything derived from your data is the ticker and
start date (your earliest purchase date) sent to Yahoo Finance. Streamlit's own usage telemetry
is turned off in `.streamlit/config.toml` (`gatherUsageStats = false`). The browser also loads the app's fonts from Google Fonts; that request carries no data from your file. `data/` is
gitignored for any real CSVs you keep locally. Never commit real statements.

## Code layout
- `streamlit_app.py`: navigation entrypoint. `app_pages/`: one file per page (UI only).
- `core/`: pure logic (`ingest`, `categorize`, `shadow`, `tvm`, `portfolios`, `risk`, `timing`, `montecarlo`, `lab` for page glue, `proof` for the live checks and the workbook) plus `prices` (yfinance + cache) and `state`.
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
  `roth_mc_kpis`, `roth_redirect` (table `redirect_table`), `landing_preview`, `proof_checks`, `proof_download`,
  `proof_process`. Chart helpers: `chart_fan`, `chart_histogram`. The Risk & CAPM and Timing test pages were
  removed on Nov 19, 2026 at Ashton's request; their engines (`core/risk.py`, `core/timing.py`, `core/lab.py`) and
  tests stay in the repo.

## Agent setup (one terminal tab each, all in this folder)
| Tab | Command | Role |
|---|---|---|
| 1 | `grok` | Designer. Reads GROK.md, then AGENTS.md. |
| 2 | `claude --add-dir ..\second-brain` | Builder. CLAUDE.md imports AGENTS.md. |
| 3 | `claude` (new session, first prompt: "You're the auditor") | Auditor, read-only. Say "audit phase N". |

Agents pass work and requests through [HANDOFF.md](HANDOFF.md).
