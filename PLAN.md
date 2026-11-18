# Plan (owned by the project lead, Claude Code)

The lead writes this plan; each agent does only its own tasks; the lead updates the status
column. Requests between agents go through HANDOFF.md. Last updated 2026-11-18.

## The goal, from the FIN 440 assignment
"Build something using AI that is meaningfully related to investments." There is no rubric beyond
the grading bands. The 100% band asks for five things, and this plan aims each phase at one:
1. **Truly incredible:** a real investments lab on the user's own spending, not a latte calculator.
2. **Understands every detail:** every number on screen has a "how it's computed" explainer.
   (Group prep comes at the end, per Ashton.)
3. **Verified every output:** a Proof page runs independent checks live, plus an Excel workbook
   with live formulas that anyone can recompute by hand.
4. **Built on class topics:** risk and return, CAPM and the SML, diversification, market
   efficiency, behavioral finance, TVM. (FIN 440 is Investments. Exact chapters still to be
   confirmed by Ashton.)
5. **Employer-grade:** tested, audited, deployed, privacy-safe, with a documented AI process.

The final submission must answer: what we built, what problem it solves, how it works, how AI
was used, what the output looks like, **how we know it's valid**, and why anyone should care.

## Who audits what
- **Grok** audits builder phases when Ashton says "audit phase N".
- **Grok's own phases** are audited by a fresh Claude subagent the lead launches.
- **Final audit:** the 3-checker team in AGENTS.md (math, leaks, design).

## Phase status
| Phase | What | Owner | State |
|---|---|---|---|
| 1 | Logic, math, tests, sample data | Builder | Done, audited, fixed |
| 2 | Design system | Grok | Done, audited; fix round = 3D.3 |
| 3 | Design pass on the first 4 pages | Grok + Builder | 3B done; 3D.1 to 3D.3 open |
| 4 | Robustness + deploy prep | Builder | Done (`0f69b4c`, `3b17e5f`) |
| 5 | Investments math engines | Builder team (3 workers) | Done, cross-checked (77 tests) |
| **6** | **New pages wired to the engines** | Builder | **Active** |
| 7 | Design for the new pages | Grok | Can start now from the page specs below |
| 8 | Proof: validation page + Excel cross-check workbook | Builder | After 6 |
| 9 | Final audit, deploy, write-up, group prep | All | Last |

## Phase 5: math engines (pure functions, no network, each with hand-checked tests)
Three workers in parallel, each owning one new module and its test file. The lead does the price
plumbing (multi-ticker fetch, risk-free rate from Yahoo `^IRX`, the 13-week T-bill) and reviews.
| ID | Module | What it computes | Hand-check tests | Status |
|---|---|---|---|---|
| 5.1 | `core/risk.py` | Returns, annualized return and volatility, Sharpe, max drawdown, beta and Jensen's alpha by regression on excess returns, CAPM expected return, SML points | Asset = 2 x market gives beta 2, alpha 0, R² 1; a known drawdown path; vol of a known series | done; beta = numpy.polyfit on 5y QQQ/SPY (1.2801) |
| 5.2 | `core/montecarlo.py` | Roth projection with random monthly returns (normal or bootstrap from history); percentile bands by age; odds of reaching a target | Zero volatility reproduces `tvm.roth_projection` exactly; mean of 20,000 paths is within 1% of the closed-form FV | done; median $528,893 vs closed form $705,071 (volatility drag, a presentation point) |
| 5.3 | `core/portfolios.py`, `core/timing.py` | Shadow portfolios with weights (e.g. 60/40), built on `shadow.build_shadow`; a market-timing test that reshuffles purchase dates 1,000 times and ranks your real timing (efficient markets: your timing is luck) | Constant prices make every shuffle equal; rising prices make earlier dates always better; weights 1.0 equal the single-fund shadow | done; 60/40 equals a brute-force recompute to the cent |
| 5.4 | `core/prices.py` (lead) | Fetch several tickers at once; risk-free rate from `^IRX`; monthly history for Monte Carlo bootstrap | Existing tests + a live smoke check | done (`f37d293`): rf 4.143% discount = 4.31% EAR |

## Page specs (Phase 6 builds them; Grok can design them now in Phase 7)
New keys follow the same `.st-key-<key>` pattern. Navigation becomes 7 pages.
| Page | Sections (keys) | Class topic |
|---|---|---|
| Shadow portfolio (extend) | add `shadow_compare`: 2 to 4 portfolios (VOO, 60/40 VOO/BND, BND, QQQ by default) on the same purchases | Diversification |
| **Risk & CAPM** (new) | `risk_kpis` (vol, Sharpe, max drawdown, beta, alpha); `chart_risk_return` (risk vs return scatter, one dot per portfolio); `chart_sml` (security market line with each portfolio's dot, alpha = distance above/below the line); `risk_explainer` | Risk/return, CAPM, SML |
| **Timing test** (new) | `timing_kpis` (your value, median shuffled value, percentile rank); `chart_timing_hist` (histogram of the 1,000 shuffles with your result marked); `timing_explainer` | Market efficiency, behavioral finance |
| Roth calculator (extend) | `roth_mc_controls`; `chart_roth_fan` (5/25/50/75/95 percentile bands); `roth_mc_kpis` (median, bad case, odds of reaching a target) | TVM under uncertainty |
| **Proof** (new) | `proof_checks` (a table of live independent checks, each pass/fail with both numbers); `proof_download` (Excel workbook with formulas); `proof_process` (how AI was used and audited, from HANDOFF) | Validation |

## Phase 8: Proof
- Live checks: Roth closed form vs the simulation; Monte Carlo mean vs the closed form; beta by
  regression vs cov/var; shadow value vs a brute-force recompute; spending total vs the raw CSV.
- Excel workbook (openpyxl, real formulas, not pasted values): FV, shadow purchases and shares,
  beta via `SLOPE`, Sharpe, so a grader can audit it in the tool the course uses.

## Open from earlier phases
- Grok: 3D.1 (page check at 1280px and 390px), 3D.2 (section 7 checklist), 3D.3 (phase 2 audit fixes).

## Needs Ashton
1. FIN 440 chapter list or syllabus topics, so every feature cites a class topic correctly.
2. Check-in dates and the presentation date, so the phases fit the calendar.
3. Deploy later (DEPLOY.md), once the new pages land.
