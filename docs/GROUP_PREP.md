---
title: "Spend Shadow group prep"
type: project-doc
updated: 2026-11-19
---

# Group prep: explain every number

Group: Ashton (project lead), Taylor and Jonathan. Ashton presents the whole deck on Nov 30.
Taylor and Jonathan should still be able to answer every block below without the app open, since
questions can go to anyone. Load the sample
(Upload, then "Use sample data") and follow along. Market figures change daily; the sample's
spending figures do not.

## Spending breakdown
- **Total $6,963.81** = every purchase in the file. Refunds and deposits are left out, not
  subtracted. Card payments and transfers don't count, since paying a card bill isn't new spending.
- **Per month $1,160.63** = total divided by 6 calendar months.
- **Discretionary $3,684.72 (53%)** = Dining + Coffee + Entertainment + Shopping + Subscriptions
  + Travel. Groceries, gas, transport, health and housing count as needs.
- *Q: Why not net refunds?* A bank CSV can't reliably tell a refund from income.

## Shadow portfolio
- Each purchase buys **fractional shares** at the close of the first trading day on or after it:
  shares = amount / price. Value today = shares x latest price, summed.
- **Adjusted closes** fold dividends back into the price, so dividends count as reinvested.
- **XIRR** is the money-weighted annual return: the rate that makes the present value of all the
  buys equal today's value. It is noisy over a few months, because annualizing a short span
  magnifies it.
- **Compare card:** the same purchases split 60/40 VOO/BND lost less than 100% VOO over this
  window. Diversification lowers the swing; it doesn't promise more return.
- *Verify:* the Proof page's brute-force loop, and the Shadow sheet of the workbook.

## Removed pages (Nov 19)
- The Risk & CAPM page and the Timing test were removed to keep the app focused on spending, the
  shadow portfolio and the Roth. Their engines and tests are still in the repo.
- *Q: Why no CAPM?* Be ready to say it was built, checked and then cut for focus; the 60/40 vs
  100% VOO compare on the Shadow page still shows diversification (Ch 7).

## Roth calculator
- **FV = PMT x ((1+r)^n - 1)/r** with r = 7%/12 and n = 528 months gives $705,070.79. That is
  exactly Excel `FV(0.07/12,528,-200)`. Annuity due multiplies by (1+r).
- **Why the return slider runs 6% to 10%:** a Roth earns whatever it holds. 7% is the usual
  long-run real (after-inflation) return for an S&P 500 fund, about 10% before inflation, and 6%
  is a conservative mix with bonds or a bad decade.
- **APR vs effective:** APR uses r/12. An effective annual rate uses (1+R)^(1/12) - 1, which is
  slightly lower per month.
- **Funded from your spending (the default with data):** the wants total $3,684.72 is the starting
  balance, and the monthly box is pre-filled with a suggestion by tier: under $200/month of wants
  suggests 50%, $200 to $500 suggests 35%, over $500 suggests 25%, rounded to $25 and capped at
  $625. The sample's $614.12/month is the heavy tier: 25% = $153.53, so $150/month. 21 to 65 at
  7%: $608,262. *Q: Why a smaller share for heavier spenders?* So the ask stays realistic: a
  quarter of a big wants budget is still more dollars than half of a small one.
- **Redirected wants table:** the sample's wants (dining, coffee, entertainment, shopping,
  subscriptions, travel) average $3,684.72 / 6 months = $614.12/month. All of it from 21 to 65
  at 7% grows to $2,164,990; 25% ($153.53) grows to $541,248; 50% to $1,082,495. $614.12 is under
  the $625/month cap, so the cap never binds. Proof checks the all-in figure against the annuity
  formula. On the page ("My spending" mode) every row also starts from the $3,684.72, so all of
  it shows $2,244,450.
- **IRA cap:** $7,500/yr ($625/month), plus $1,100 from age 50. When the cap binds, "Show the
  math" splits the payments into segments, each grown to retirement.
- **Monte Carlo:** 5,000 paths with random monthly returns that average 7%/yr.
  - The mean lands next to $705k, which is the check.
  - The median ($518k) is lower because of volatility drag: -50% then +50% leaves you at 75%.
  - The 5th percentile is the bad case.
  - Only 34% of paths reach $705k.
- *Q: Real vs nominal?* A real (after-inflation) return keeps the answers in today's dollars. The
  bootstrap view replays nominal fund months.

## Proof page
- 8 checks on the sample. Each pairs an app number with a recompute that doesn't use the app's
  own code for it: a raw CSV re-read, plain loops (VOO and 60/40), Excel's FV, the annuity formula
  (default Roth and the redirected-wants Roth), PV plus annuity for the suggested plan, and the Monte Carlo mean within 3 standard errors.
  Each reports pass or fail with both numbers.
- A real upload gets 7 checks. The raw file isn't kept, so the spending check runs on the sample only.
- *Q: Is every number live-checked?* No, and the page says so. XIRR, BND/SCHD and the Monte Carlo
  percentiles were recomputed by hand in the final audit.
- The Excel workbook uses live formulas. We recalculated it in Excel, and every difference is 0.
- *Q: How do you know AI didn't hallucinate?*
  - Every output was recomputed outside the code.
  - Separate agents audited each other's work.
  - Real Excel caught a bug the tests had missed (`#NAME?` on `STDEV.S`).
  - The final audit caught a circular check (an engine compared with itself), and it was replaced.

## How AI was used (be ready to tell this)
- One AI built, one designed, and a third audited. No agent graded its own work.
- Rules, handoffs and audit results are all in the repo (`AGENTS.md`, `HANDOFF.md`, `PLAN.md`).
- People made every scope and ship decision.

## Class check-ins (be ready for these questions)
**Game plan check-in**
- *The idea:* turn a bank or card statement into an investments lab on your own spending.
- *How it relates to investments:* it covers returns, risk, CAPM, diversification, market
  efficiency and TVM (BKM Ch 2, 5, 6, 7, 9, 11, 12).
- *AI tools:*
  - Claude Code built the app.
  - Grok designed the look.
  - Each audited the other.
- *How we avoid slop:*
  - hand-checked tests (Excel FV, brute-force loops, numpy);
  - an independent audit every phase;
  - a live Proof page;
  - an Excel workbook built from formulas.
- *Challenges we expected:*
  - bank CSV formats vary, so the app auto-detects the columns;
  - a short purchase window makes the statistics noisy, so there's a 5-year view;
  - privacy.

**Progress check-in**
- *Built and working:* all 7 pages, live at the Streamlit URL, with 92 tests passing.
- *What changed:*
  - Plaid and email scraping became CSV upload: no credentials, any bank, data stays in the session.
  - The scope grew from a calculator into an investments lab.
- *What didn't work at first, and how we caught it:*
  - the Roth cap ignored the age-50 catch-up;
  - a loss displayed as a gain;
  - the SML sloped downward with no explanation;
  - Excel showed `#NAME?`;
  - one Proof check was circular.
- *What's left:* the presentation deck, and practice explaining each number.

## Chapter map (cite only covered chapters: 1, 2, 3, 5, 6, 7, 9, 11, 12)
Since the Nov 19 cut, the app itself shows Ch 1, 2, 5, 7 and 12. Ch 6, 9 and 11 were the Risk &
CAPM and Timing pages; mention them only as "built, then removed".
- **Ch 2:** T-bills (bank discount yield), stock and bond indexes, asset classes.
- **Ch 5:** holding-period return, compounding, APR vs EAR, real vs nominal, standard deviation,
  Sharpe ratio, arithmetic vs geometric averages (volatility drag), the normal distribution.
- **Ch 6:** the risk-free asset vs risky assets, capital allocation.
- **Ch 7:** efficient diversification, the stock-bond mix, systematic vs diversifiable risk.
- **Ch 9:** CAPM, beta, alpha, the security market line.
- **Ch 11:** the efficient market hypothesis (the timing test).
- **Ch 12:** behavioral finance (impulse spending, overconfidence in timing).
- **Not covered, so don't cite them:**
  - Ch 4: ETFs as investment companies. Say "asset classes, Ch 2" instead.
  - Ch 8: estimating beta by regression. Say "beta, Ch 9".
  - Ch 10.
