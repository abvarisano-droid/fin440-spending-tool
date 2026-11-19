---
title: "Spend Shadow write-up"
type: project-doc
updated: 2026-11-19
---

# Spend Shadow: FIN 440 project write-up

**Live app:** https://fin440-spending-to-uaoynqbehwjlulmegnfrpf.streamlit.app/ (click "Use sample data" on the first page)

*Draft for the group. Market figures use Yahoo Finance prices as of Nov 18, 2026 and move daily;
spending figures come from the fictional sample file and never change.*

## 1. What we built
Spend Shadow is a web app that turns a bank or card statement into an investments lab. Upload a
CSV export (or use the fictional sample) and it answers one question several ways: **what is your
spending really costing you as an investor?**

Five pages:
1. **Upload:** reads any bank or card CSV and auto-detects the date, merchant and amount columns.
   Before anything is loaded it plays a one-minute tutorial: six captioned steps on a fictional statement.
2. **Spending breakdown:** totals, categories, needs vs. wants.
3. **Shadow portfolio:** what every purchase would be worth had it bought an index fund that day,
   compared across four portfolios.
4. **Roth calculator:** time value of money, fixed and with uncertain returns (Monte Carlo), and
   what your own wants spending would grow to if you redirected it into a Roth.
5. **Proof:** live checks of the key numbers plus an Excel workbook with real formulas.

## 2. The problem it solves
People hear "invest instead of spending" as abstract advice. Spend Shadow makes it concrete and
personal: the purchases are yours, the dates are yours, and the prices are real. It also avoids
the usual "latte calculator" trap of assuming a smooth 7%. It shows a range of outcomes, and it
turns your actual wants spending into a retirement number.

## 3. How it works (and the class topic behind each part)
Chapters refer to Bodie, Kane & Marcus, *Investments*, 13th edition, as covered in FIN 440.

| Page | What it computes | BKM 13e chapters |
|---|---|---|
| Spending breakdown | Gross purchases by category; discretionary (wants) share | Ch 1 (saving vs. consumption), Ch 12 (impulse spending, mental accounting) |
| Shadow portfolio | Each purchase buys fractional shares at the first close on or after its date, using dividend-adjusted prices (dividends reinvested). Value today, gain, money-weighted return (XIRR) | Ch 2 (asset classes, stock and bond indexes), Ch 5 (holding-period returns, compounding) |
| Shadow: compare | The same purchases split 100% VOO, 60/40 VOO/BND, 100% BND, 100% QQQ | Ch 7 (efficient diversification: the stock-bond mix) |
| Roth calculator | FV of a monthly annuity with the 2026 IRA limit and age-50 catch-up; APR vs. effective rate; ordinary annuity vs. annuity due; 25%, 50% and all of your discretionary average redirected | Ch 5 (compounding, APR vs. EAR, real vs. nominal returns) |
| Roth: uncertain returns | 5,000 simulated paths (normal returns, or replayed real fund months); percentile bands; odds of a target | Ch 5 (normal distribution, arithmetic vs. geometric averages: volatility drag) |

One technical choice matters for correctness: every purchase buys at the first close on or after
its date, using dividend-adjusted prices, so the shadow value is what that exact purchase stream
would hold today, and the money-weighted return (XIRR) accounts for when each dollar went in.


## What changed from the original plan
- **Plaid and email or Shop Pay scraping became CSV upload.** Plaid needs API keys, a developer
  account and bank logins, and reading email needs inbox access. A CSV export works with any bank
  or card, needs no credentials, and keeps the data in the browser session. Another person can
  still run it on their own real data, which was the goal.
- **The scope grew from "spending and a Roth calculator" into an investments lab.** We added
  a diversification comparison, Monte Carlo uncertainty and a Proof page. Each addition ties back
  to a course chapter.
- **We built, then removed, a Risk & CAPM page and a market-timing test (Nov 19)** to keep the
  app focused on spending, the shadow portfolio and the Roth. The engines and their tests are
  still in the repository.
- **The Roth default is ages 21 to 65.** It is editable, so 60 is one click away.

## 4. How AI was used
We built this with three AI agents, each with its own job and its own files:
- **Builder (Claude Code):** wrote the app logic, the math engines and the tests.
- **Designer (Grok):** designed the look: the colors, fonts, layout and chart styling.
- **Auditor:** a separate, read-only Claude session reviewed each phase, reported, and never
  fixed anything, so no agent graded its own work. It ran the final audit and the Nov 19 re-audits.
  Grok also audited some of Claude's earlier phases (logged in `HANDOFF.md`).

The agents coordinated through a written rulebook (`AGENTS.md`), an append-only log of every
handoff and audit (`HANDOFF.md`) and a phase plan (`PLAN.md`), all in the repository. The group
made the decisions: scope, class topics, what to fix and what ships.

The audits caught real errors before they shipped:
- The Roth contribution cap ignored the age-50 catch-up.
- A loss on the shadow portfolio displayed as a green gain.
- Dollar signs in text rendered as math formulas.
- The chart palette had fewer colors than spending categories, so two categories shared a color.
- The security market line sloped downward with no explanation.
- The Excel workbook showed `#NAME?` until a function-prefix bug was fixed.
- One Proof check compared an engine with itself, which is circular. It now compares against
  an independent loop.

## 5. What the output looks like (on the sample file)
- **Spending:** $6,963.81 over 6 months ($1,160.63/month). Wants are 53% ($3,684.72). Top
  categories: Shopping $2,052, Groceries $1,627, Dining $764.
- **Shadow portfolio:** the same $6,963.81 in VOO would be worth about $6,749 today (-3.1%). The
  60/40 mix lost less (-2.1%), BND least (-0.6%), and QQQ most (-8.0%). Over a short window,
  diversification shows up as a smaller swing, not a bigger gain.
- **Roth:**
  - $200/month from 21 to 65 at 7% grows to $705,071 (Excel `FV(0.07/12, 528, -200)`).
  - The sample's wants average $614.12/month. Redirecting all of it grows to $2,164,990; 25%
    ($153.53/month) grows to about $541,248.
  - With uncertain returns (15% volatility), the median outcome is $517,725, the 5th percentile
    is $163,563, and only 34% of paths reach the $705k a simple calculator promises.

## 6. How we know it's valid
1. **Hand-checked tests (94).** Expected values come from outside the code: Excel `FV`, hand
   formulas, brute-force loops, `numpy.polyfit`. For example, Roth $705,070.79 equals Excel's FV
   to the cent, and the 60/40 portfolio equals a purchase-by-purchase recompute to $0.000001.
2. **Independent audits every phase,** plus a final three-checker audit (math, data leaks,
   design) by fresh agents that had not seen the code before.
3. **A live Proof page.** It runs 7 checks on the sample (6 on an upload). Each pairs an app
   number with a recompute that doesn't use the app's own code for it:
   - the spending total vs. a raw re-read of the CSV;
   - the VOO and 60/40 portfolio values vs. plain loops;
   - the Roth balance vs. Excel's FV and the annuity formula;
   - the redirected-wants Roth balance vs. the annuity formula;
   - the Monte Carlo mean within 3 standard errors of the closed form.

   The final math audit flagged a check that compared one engine with itself; we replaced it. The
   page also says plainly which numbers are verified by the audit rather than live.
4. **An Excel workbook with live formulas** (`FV`, shares and value per purchase). We
   recalculated it in Excel itself: every difference cell is 0.
5. **A built-in sanity anchor on screen.** The Monte Carlo average lands next to the
   fixed-return formula, and the page shows both numbers.

## 7. Why it matters
- **For a person:** it turns "spend less" into a number with a risk range attached, using their
  own data.
- **For the class:** it applies index investing, holding-period and money-weighted returns,
  stock-bond diversification and TVM under uncertainty to real prices and real spending.
- **For an employer:** it shows tested, audited and documented financial software, with privacy
  by design and a documented process for using AI safely: verify every output, separate building
  from auditing, keep an audit trail.

## Limitations
- No fees, taxes or bid-ask spreads.
- Prices come from Yahoo Finance, a free data source.
- The purchase window is usually short, so annualized figures are noisy; the page says so.
- Roth income limits are not checked.
- It is a what-if tool, not advice.
