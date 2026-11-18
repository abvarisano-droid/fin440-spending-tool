# Group prep: explain every number

Each member should be able to answer every block below without the app open. Load the sample
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

## Risk & CAPM
- **Volatility** = sample std of daily returns x sqrt(252).
- **Sharpe** = (average daily return - daily T-bill rate) / std x sqrt(252): excess return per
  unit of total risk.
- **Max drawdown** = the worst fall from a previous high.
- **Beta** = the slope of the portfolio's excess returns on SPY's excess returns (in Excel,
  `SLOPE`). Beta 1 moves with the market; BND is about 0.1.
- **Jensen's alpha** = the regression intercept x 252. Positive means it beat what its beta asked for.
- **CAPM:** E[R] = rf + beta (E[Rm] - rf). The **SML** plots that line. Dots above it earned
  positive alpha.
- **T-bill:** Yahoo's ^IRX is a bank discount yield. Price = 1 - d x 91/360; holding-period return
  = 1/price - 1; effective annual = (1 + HPR)^(365/91) - 1. So 4.145% discount = 4.32% effective.
- **Unit value:** risk is measured on value per unit (like a fund's NAV), so new purchases don't
  look like returns.
- *Q: Why does the line slope down on purchase dates?* Over those 6 months SPY returned less than
  T-bills. That is a negative realized risk premium. CAPM is about expected returns, so use the
  5-year view.
- *Q: Why two alphas?* "Above SML" uses compounded returns; Jensen's alpha is an arithmetic
  regression intercept. They are close but not identical.

## Timing test
- Each of 1,000 shuffles moves every purchase to a random trading day between the first and last
  real buy, then values it the same way as the shadow portfolio.
- **Percentile** = share of shuffles the real dates beat. 37th means "ordinary luck". 5th to 95th
  is the luck band. The two-sided p-value is 0.74.
- **Lump sum** (all money on day one) beats spreading purchases out in a rising market. That is
  drift, not skill.
- *Q: What does this prove?* Purchase dates carry no information about future prices, which is
  what weak-form efficiency predicts.

## Roth calculator
- **FV = PMT x ((1+r)^n - 1)/r** with r = 7%/12 and n = 528 months gives $705,070.79. That is
  exactly Excel `FV(0.07/12,528,-200)`. Annuity due multiplies by (1+r).
- **APR vs effective:** APR uses r/12. An effective annual rate uses (1+R)^(1/12) - 1, which is
  slightly lower per month.
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
- 10 checks. Each pairs an app number with a recompute that doesn't use that engine: a raw CSV
  re-read, a plain loop, numpy, Excel's FV, or a second engine. Each reports pass or fail with
  both numbers.
- The Excel workbook uses live formulas. We recalculated it in Excel, and every difference is 0.
- *Q: How do you know AI didn't hallucinate?*
  - Every output was recomputed outside the code.
  - Separate agents audited each other's work.
  - Real Excel caught a bug the tests had missed (`#NAME?` on `STDEV.S`).

## How AI was used (be ready to tell this)
- One AI built, one designed, and a third audited. No agent graded its own work.
- Rules, handoffs and audit results are all in the repo (`AGENTS.md`, `HANDOFF.md`, `PLAN.md`).
- People made every scope and ship decision.
