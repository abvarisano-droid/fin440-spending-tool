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

Seven pages:
1. **Upload:** reads any bank or card CSV and auto-detects the date, merchant and amount columns.
2. **Spending breakdown:** totals, categories, needs vs. wants.
3. **Shadow portfolio:** what every purchase would be worth had it bought an index fund that day,
   compared across four portfolios.
4. **Risk & CAPM:** volatility, Sharpe, drawdown, beta, alpha and the security market line.
5. **Timing test:** a market-efficiency experiment on your own purchase dates.
6. **Roth calculator:** time value of money, fixed and with uncertain returns (Monte Carlo).
7. **Proof:** live checks of every engine plus an Excel workbook with real formulas.

## 2. The problem it solves
People hear "invest instead of spending" as abstract advice. Spend Shadow makes it concrete and
personal: the purchases are yours, the dates are yours, and the prices are real. It also avoids
the usual "latte calculator" trap of assuming a smooth 7%. It shows risk, a range of outcomes,
and whether the market paid you for the risk you would have taken.

## 3. How it works (and the class topic behind each part)
Chapters refer to Bodie, Kane & Marcus, *Investments*, 13th edition, as covered in FIN 440.

| Page | What it computes | BKM 13e chapters |
|---|---|---|
| Spending breakdown | Gross purchases by category; discretionary (wants) share | Ch 1 (saving vs. consumption), Ch 12 (impulse spending, mental accounting) |
| Shadow portfolio | Each purchase buys fractional shares at the first close on or after its date, using dividend-adjusted prices (dividends reinvested). Value today, gain, money-weighted return (XIRR) | Ch 2 (asset classes, stock and bond indexes), Ch 5 (holding-period returns, compounding) |
| Shadow: compare | The same purchases split 100% VOO, 60/40 VOO/BND, 100% BND, 100% QQQ | Ch 7 (efficient diversification: the stock-bond mix) |
| Risk & CAPM | Volatility, Sharpe ratio, max drawdown, beta and alpha against SPY; the security market line, with the 13-week T-bill as the risk-free rate (bank discount yield converted to an effective annual rate) | Ch 2 (T-bill discount yield), Ch 5 (standard deviation, Sharpe ratio), Ch 6 (risk-free vs. risky assets), Ch 7 (systematic vs. diversifiable risk), Ch 9 (CAPM, beta, alpha, SML) |
| Timing test | Moves every purchase to a random trading day 1,000 times and ranks your real dates | Ch 11 (efficient market hypothesis, weak form), Ch 12 (overconfidence in timing) |
| Roth calculator | FV of a monthly annuity with the 2026 IRA limit and age-50 catch-up; APR vs. effective rate; ordinary annuity vs. annuity due | Ch 5 (compounding, APR vs. EAR, real vs. nominal returns) |
| Roth: uncertain returns | 5,000 simulated paths (normal returns, or replayed real fund months); percentile bands; odds of a target | Ch 5 (normal distribution, arithmetic vs. geometric averages: volatility drag) |

Two technical choices matter for correctness:
- **Time-weighted unit value.** A portfolio that keeps receiving new purchases has a balance that
  jumps whenever money goes in, and those jumps are not returns. Risk is therefore measured on a
  unit value, the way a mutual fund computes NAV, so only investment performance counts.
- **Two risk windows.** Your purchase dates (real, but often only months of data) or five years
  of fund history (statistically steadier).


## What changed from the original plan
- **Plaid and email or Shop Pay scraping became CSV upload.** Plaid needs API keys, a developer
  account and bank logins, and reading email needs inbox access. A CSV export works with any bank
  or card, needs no credentials, and keeps the data in the browser session. Another person can
  still run it on their own real data, which was the goal.
- **The scope grew from "spending and a Roth calculator" into an investments lab.** We added
  risk, CAPM and the SML, a diversification comparison, a market-efficiency test, Monte Carlo
  uncertainty and a Proof page. Each addition ties back to a course chapter.
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
- **Risk & CAPM, last 5 years:**
  - VOO: 17.1% volatility, beta 0.99, Sharpe 0.44, worst drawdown -24.5%.
  - 60/40: volatility falls to 11.0% and beta to 0.62.
  - QQQ: beta 1.28, but a negative alpha (-0.5%/yr). It took more market risk and was paid
    slightly less than CAPM required.
  - Over the 6-month purchase window, SPY returned less than T-bills, so the security market line
    sloped downward. The page explains this as a negative realized market risk premium, which can
    happen over short windows even though the expected premium is positive.
- **Timing test:** the real purchase dates beat 37% of 1,000 random ones (p = 0.74). That is what
  luck looks like, consistent with market efficiency. Every random set landed between about
  $6,712 and $6,791, so for small, steady purchases timing barely matters. Investing everything
  on day one would have produced about $7,095. That is the drift of a rising market, not skill.
- **Roth:**
  - $200/month from 21 to 65 at 7% grows to $705,071 (Excel `FV(0.07/12, 528, -200)`).
  - Redirecting 25% of the sample's wants ($153.53/month) grows to about $541,000.
  - With uncertain returns (15% volatility), the median outcome is $517,725, the 5th percentile
    is $163,563, and only 34% of paths reach the $705k a simple calculator promises.

## 6. How we know it's valid
1. **Hand-checked tests (90).** Expected values come from outside the code: Excel `FV`, hand
   formulas, brute-force loops, `numpy.polyfit`. For example, Roth $705,070.79 equals Excel's FV
   to the cent, and the 60/40 portfolio equals a purchase-by-purchase recompute to $0.000001.
2. **Independent audits every phase,** plus a final three-checker audit (math, data leaks,
   design) by fresh agents that had not seen the code before.
3. **A live Proof page.** It runs 10 checks on your own data. Each pairs an app number with a
   recompute that doesn't use the app's own code for it:
   - the spending total vs. a raw re-read of the CSV;
   - the VOO and 60/40 portfolio values vs. plain loops;
   - the timing test vs. the shadow value;
   - beta vs. numpy covariance/variance;
   - volatility and Sharpe vs. hand formulas;
   - the Roth balance vs. Excel's FV and the annuity formula;
   - the Monte Carlo mean within 3 standard errors of the closed form.

   The final math audit flagged a check that compared one engine with itself; we replaced it. The
   page also says plainly which numbers are verified by the audit rather than live.
4. **An Excel workbook with live formulas** (`FV`, shares and value per purchase, `SLOPE`,
   `STDEV.S`, the T-bill conversion, Sharpe). We recalculated it in Excel itself: every
   difference cell is 0, to about 16 decimal places.
5. **Built-in sanity anchors on screen.** SPY sits exactly on its own security market line. The
   Monte Carlo average lands next to the fixed-return formula, and the page shows both numbers.

## 7. Why it matters
- **For a person:** it turns "spend less" into a number with a risk range attached, using their
  own data.
- **For the class:** it applies CAPM, the SML, diversification, market efficiency and TVM to real
  prices and shows where the theory holds and where a short window breaks it.
- **For an employer:** it shows tested, audited and documented financial software, with privacy
  by design and a documented process for using AI safely: verify every output, separate building
  from auditing, keep an audit trail.

## Limitations
- No fees, taxes or bid-ask spreads.
- Prices come from Yahoo Finance, a free data source.
- The purchase window is usually short, so annualized figures are noisy; the page says so.
- Roth income limits are not checked.
- It is a what-if tool, not advice.
