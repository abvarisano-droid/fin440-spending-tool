import json
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

OUT = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(f"{OUT}/numbers.json"))
URL = "https://fin440-spending-to-uaoynqbehwjlulmegnfrpf.streamlit.app/"

def rgb(h): return RGBColor.from_string(h.lstrip("#"))
PAPER, INK, MUTED, PINE, ORANGE, BLUE, TINT, LINE = "#F4EFE6", "#1C1915", "#6E675C", "#1E4A3A", "#B45309", "#2C4A6E", "#EDE6D9", "#DDD4C6"
SERIF, SANS = "Georgia", "Arial"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, runs, size=18, color=INK, font=SANS, bold=False, align=None, spacing=None):
    """runs: str, or list of paragraphs; each paragraph is a str or (str, dict(size,color,bold,font))."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        txt, st = (para, {}) if isinstance(para, str) else para
        r = p.add_run(); r.text = txt
        r.font.size = Pt(st.get("size", size)); r.font.name = st.get("font", font)
        r.font.bold = st.get("bold", bold); r.font.color.rgb = rgb(st.get("color", color))
        if align: p.alignment = align
        if spacing: p.space_after = Pt(spacing)
    return tb


def slide(title, kicker=None, notes=""):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(PAPER)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), prs.slide_height)
    bar.fill.solid(); bar.fill.fore_color.rgb = rgb(PINE); bar.line.fill.background()
    if kicker:
        text(s, 0.6, 0.35, 12, 0.4, kicker.upper(), size=12, color=MUTED, bold=True)
    text(s, 0.6, 0.65, 12.2, 1.0, title, size=30, color=PINE, font=SERIF)
    s.notes_slide.notes_text_frame.text = notes
    return s


def card(s, x, y, w, h, big, label, color=PINE):
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = rgb(TINT); box.line.color.rgb = rgb(LINE)
    text(s, x + 0.15, y + 0.12, w - 0.3, 0.7, big, size=28, color=color, font=SERIF)
    text(s, x + 0.15, y + 0.85, w - 0.3, h - 0.9, label, size=13, color=MUTED)


def bullets(s, x, y, w, h, items, size=18):
    text(s, x, y, w, h, [("•  " + i if not i.startswith("   ") else i) for i in items], size=size, spacing=10)


def chapters(s, txt):
    text(s, 0.6, 6.85, 12, 0.4, "BKM 13e: " + txt, size=12, color=MUTED)


P = N["ports"]; T = N["t5"]; TT = N["tt"]; R = N["roth"]
pct = lambda v: f"{v:+.1%}"

# 1 title
s = slide("", notes=(
    "Open with the hook: we all hear 'spend less and invest the difference', but nobody can feel it. "
    "Spend Shadow takes a real bank statement and shows what that spending costs you as an investor, "
    "with real prices, real risk, and every number checked."))
text(s, 0.9, 1.7, 11.5, 1.4, "Spend Shadow", size=60, color=PINE, font=SERIF)
text(s, 0.9, 2.9, 11.5, 1.0, "What your spending really costs you as an investor", size=26, color=INK, font=SERIF)
text(s, 0.9, 4.2, 11.5, 1.6, [
    "FIN 440 Investments  ·  Prof. Van Alfen  ·  Fall 2026",
    ("Live app: " + URL, {"size": 16, "color": BLUE}),
    ("Group: [names]", {"size": 16, "color": MUTED}),
], size=18, color=MUTED, spacing=8)

# 2 problem
s = slide("\"Spend less and invest\" is advice nobody can feel", "The problem", notes=(
    "Spending is concrete, investing is abstract. Typical calculators assume a smooth 7% with no risk. "
    "We wanted the user's own purchases, their own dates, real market prices, and an honest range of outcomes."))
bullets(s, 0.6, 1.9, 7.2, 4.5, [
    "Spending is concrete. Investing is abstract.",
    "Typical \"latte calculators\" assume a smooth 7% a year: no risk, no range, no market reality.",
    "We wanted: your purchases, your dates, real prices, real risk, and proof the math is right.",
])
card(s, 8.4, 1.9, 4.3, 1.9, "$705,071", "what a fixed-7% calculator promises for $200/mo, age 21 to 65")
card(s, 8.4, 4.0, 4.3, 1.9, f"{R['odds']:.0%}", "of 5,000 realistic market paths actually get there", color=ORANGE)

# 3 what we built
s = slide("An investments lab built on your own bank statement", "What we built", notes=(
    "Seven pages. Upload any bank CSV, or the fictional sample. Each lab page ties to a course chapter, "
    "shown on the page itself. Proof is the page that shows the math is right."))
pages = [("Upload", "any bank or card CSV, columns auto-detected", ""),
         ("Spending breakdown", "categories, needs vs. wants", "Ch 1, 12"),
         ("Shadow portfolio", "every purchase as if it bought a fund that day; 4 portfolios compared", "Ch 2, 5, 7"),
         ("Risk & CAPM", "volatility, Sharpe, drawdown, beta, alpha, the SML", "Ch 2, 5, 6, 7, 9"),
         ("Timing test", "your dates vs. 1,000 random ones", "Ch 11, 12"),
         ("Roth calculator", "TVM with the IRA cap, plus Monte Carlo uncertainty", "Ch 5"),
         ("Proof", "10 live independent checks + an Excel workbook of formulas", "validation")]
for i, (name, desc, ch) in enumerate(pages):
    y = 1.85 + i * 0.68
    text(s, 0.6, y, 3.4, 0.6, name, size=19, color=PINE, font=SERIF)
    text(s, 4.0, y + 0.04, 6.9, 0.6, desc, size=16)
    text(s, 11.0, y + 0.06, 2.1, 0.6, ch, size=13, color=MUTED, align=PP_ALIGN.RIGHT)

# 4 how it works
s = slide("How it works", "Under the hood", notes=(
    "Walk the pipeline left to right. The key design choice: risk is measured on a time-weighted unit value, "
    "the way a mutual fund computes NAV, so a new purchase never looks like a return. Only tickers and a "
    "start date ever leave the browser session."))
steps = [("1  Read", "CSV upload, auto-detected columns, purchases only"), ("2  Categorize", "13 categories; wants vs. needs"),
         ("3  Shadow buy", "first close on/after each purchase, dividend-adjusted (Yahoo)"),
         ("4  Measure risk", "vs. SPY and the 13-week T-bill"), ("5  Project", "TVM + 5,000 Monte Carlo paths"),
         ("6  Prove", "live independent checks + Excel")]
for i, (h, d) in enumerate(steps):
    x = 0.6 + i * 2.1
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(2.0), Inches(1.95), Inches(2.3))
    box.fill.solid(); box.fill.fore_color.rgb = rgb(TINT); box.line.color.rgb = rgb(LINE)
    text(s, x + 0.12, 2.1, 1.75, 0.5, h, size=16, color=PINE, font=SERIF, bold=True)
    text(s, x + 0.12, 2.65, 1.75, 1.6, d, size=13)
bullets(s, 0.6, 4.75, 12.2, 2, [
    "Time-weighted unit value (like a fund's NAV): new purchases never count as returns.",
    "T-bill bank discount yield converted to an effective annual rate: 4.145% discount = 4.32% EAR.",
    "Privacy: your file stays in your browser session; only tickers and a start date go to Yahoo Finance.",
], size=16)
chapters(s, "Ch 2 (T-bills, indexes), Ch 5 (HPR, APR vs. EAR)")

# 5 spending
s = slide("The sample: $6,963.81 in six months, 53% of it wants", "Output: spending", notes=(
    "This is the fictional sample anyone can load. Wants are dining, coffee, entertainment, shopping, "
    "subscriptions, travel. Refunds are excluded, not netted: a bank CSV can't reliably tell a refund from income."))
card(s, 0.6, 1.9, 3.6, 1.6, f"${N['total']:,.2f}", "total purchases, May to Oct 2026")
card(s, 0.6, 3.7, 3.6, 1.6, f"${N['monthly']:,.2f}", "per month")
card(s, 0.6, 5.5, 3.6, 1.2, f"${N['disc']:,.2f}", "wants (53%)", color=ORANGE)
s.shapes.add_picture(f"{OUT}/spending.png", Inches(4.6), Inches(1.75), height=Inches(5.0))
chapters(s, "Ch 1 (saving vs. consumption), Ch 12 (impulse spending, mental accounting)")

# 6 shadow + diversification
s = slide("Same purchases, four portfolios: diversification is a smaller swing", "Output: shadow portfolio", notes=(
    "Every purchase buys fractional shares at the first close on or after its date. Over this six-month "
    "window the market was choppy, so every portfolio is slightly under what was spent; QQQ swings most, "
    f"BND least. Prices as of {N['asof']}; they move daily."))
s.shapes.add_picture(f"{OUT}/compare.png", Inches(0.6), Inches(1.7), width=Inches(8.6))
for i, (n, (v, r)) in enumerate(P.items()):
    card(s, 9.5, 1.7 + i * 1.25, 3.3, 1.15, f"${v:,.0f}", f"{n}  ({pct(r)})", color={0: ORANGE, 1: BLUE, 2: MUTED, 3: PINE}[i])
chapters(s, "Ch 2 (asset classes, indexes), Ch 5 (holding-period returns), Ch 7 (stock-bond diversification)")

# 7 CAPM
v, q, sf = T["100% VOO"], T["100% QQQ"], T["60/40 VOO/BND"]
s = slide("CAPM holds over 5 years, and breaks over 6 months", "Output: risk and CAPM", notes=(
    f"Left: 5 years. The SML runs from the T-bill ({N['rf']:.2%}) through SPY ({N['mk5']:.1%}). VOO sits on it "
    f"(beta {v['beta']:.2f}). QQQ took more market risk (beta {q['beta']:.2f}) but landed below the line: alpha "
    f"{q['alpha_annual']:+.1%}/yr. The 60/40 mix cut volatility from {v['ann_vol']:.1%} to {sf['ann_vol']:.1%}. "
    f"Right: over our 6-month window SPY returned {N['mkw']:.1%}, less than T-bills, so the line slopes DOWN: "
    "a negative realized risk premium. CAPM is about expected returns; short windows can do this. "
    "Beta is estimated by regression; we cite it as Ch 9."))
s.shapes.add_picture(f"{OUT}/sml.png", Inches(0.6), Inches(1.6), width=Inches(9.0))
bullets(s, 9.85, 1.75, 3.3, 5, [
    f"VOO: beta {v['beta']:.2f}, Sharpe {v['sharpe']:.2f}",
    f"QQQ: beta {q['beta']:.2f}, alpha {q['alpha_annual']:+.1%}/yr",
    f"60/40: vol {v['ann_vol']:.0%} to {sf['ann_vol']:.0%}",
    f"6 months: market {N['mkw']:.1%} < T-bill {N['rf']:.1%}, so the SML slopes down",
], size=15)
chapters(s, "Ch 5 (std. dev., Sharpe), Ch 6 (risk-free asset), Ch 7 (systematic risk), Ch 9 (CAPM, beta, alpha, SML)")

# 8 timing
s = slide("Your purchase timing looks exactly like luck", "Output: timing test", notes=(
    "We moved every purchase to a random trading day, 1,000 times. The real dates beat 37% of the random ones, "
    f"p = {TT['p_value_two_sided']:.2f}: squarely inside the luck band, what weak-form efficiency predicts. "
    f"All 1,000 landed between ${TT['lo']:,.0f} and ${TT['hi']:,.0f}, so for small steady purchases timing barely "
    f"matters. Lump sum on day one would be ${TT['lump_sum_value']:,.0f}: that is market drift, not skill."))
s.shapes.add_picture(f"{OUT}/timing.png", Inches(0.6), Inches(1.6), width=Inches(8.8))
card(s, 9.7, 1.7, 3.1, 1.4, f"{TT['percentile']:.0%}", f"of random dates beaten (p = {TT['p_value_two_sided']:.2f})")
card(s, 9.7, 3.3, 3.1, 1.4, f"${TT['hi'] - TT['lo']:,.0f}", "spread across all 1,000 shuffles")
card(s, 9.7, 4.9, 3.1, 1.4, f"${TT['lump_sum_value']:,.0f}", "all-in on day one (drift, not skill)", color=ORANGE)
chapters(s, "Ch 11 (efficient market hypothesis, weak form), Ch 12 (overconfidence in timing)")

# 9 roth
s = slide("A calculator says $705k. Reality is a range.", "Output: Roth IRA", notes=(
    "Fixed 7%: $200/month from 21 to 65 is $705,071, exactly Excel FV(0.07/12, 528, -200). With 15% volatility "
    f"and the same 7% average, the average outcome stays near $705k (${R['mean']:,.0f}), but the median is "
    f"${R['p50']:,.0f}: volatility drag, because -50% then +50% leaves you at 75%. Bad case (5th percentile) "
    f"${R['p5']:,.0f}. Only {R['odds']:.0%} of paths reach the calculator's number."))
s.shapes.add_picture(f"{OUT}/fan.png", Inches(0.6), Inches(1.6), width=Inches(8.8))
card(s, 9.7, 1.7, 3.1, 1.25, f"${R['fv']:,.0f}", "fixed 7% (Excel FV)", color=ORANGE)
card(s, 9.7, 3.1, 3.1, 1.25, f"${R['p50']:,.0f}", "median of 5,000 paths")
card(s, 9.7, 4.5, 3.1, 1.25, f"${R['p5']:,.0f}", "bad case (5th percentile)")
card(s, 9.7, 5.9, 3.1, 0.85, f"{R['odds']:.0%} reach $705k", "", color=ORANGE)
chapters(s, "Ch 5 (compounding, APR vs. EAR, arithmetic vs. geometric averages)")

# 10 AI
s = slide("How AI was used: build, design, audit, never grade your own work", "Process", notes=(
    "Three agents with separate jobs and separate files. Claude Code wrote the logic, engines and tests; Grok "
    "designed the look; each audited the other's phases, so nobody graded their own work. Everything was "
    "coordinated in writing in the repo. People made every scope and ship decision."))
cols = [("Builder", "Claude Code", "App logic, math engines, 92 tests"),
        ("Designer", "Grok", "Colors, type, layout, chart styling"),
        ("Auditor", "the other agent", "Reviews every phase; reports, never fixes")]
for i, (role, who, what) in enumerate(cols):
    x = 0.6 + i * 4.2
    card(s, x, 1.9, 3.9, 2.0, role, f"{who}: {what}")
bullets(s, 0.6, 4.3, 12.2, 2.4, [
    "Written rules (AGENTS.md), an append-only handoff and audit log (HANDOFF.md), a phase plan (PLAN.md).",
    "Final audit: three fresh checkers in parallel, for math, data leaks and design.",
    "Humans decided scope, class topics, what to fix and what ships.",
], size=17)

# 11 validity
s = slide("How we know the output is valid", "Proof", notes=(
    "'The AI did it' is not evidence. Four layers: hand-worked tests with expected values from outside the "
    "code; an independent audit every phase; a Proof page that re-checks key numbers live on your own data; "
    "and an Excel workbook of real formulas we recalculated in Excel itself."))
card(s, 0.6, 1.9, 2.9, 1.7, "92", "tests with hand-worked expected values (Excel FV, loops, numpy)")
card(s, 3.7, 1.9, 2.9, 1.7, "10 / 10", "live checks pass on the Proof page")
card(s, 6.8, 1.9, 2.9, 1.7, "0.00", "difference, Excel formulas vs. the app")
card(s, 9.9, 1.9, 2.9, 1.7, "3", "fresh checkers in the final audit: math, data leaks, design")
bullets(s, 0.6, 4.0, 12.2, 2.8, [
    "Each live check pairs an app number with a recompute that doesn't use the app's own code for it.",
    "Built-in anchors: SPY sits exactly on its own SML; the Monte Carlo mean lands on the closed form.",
    "The page says which numbers are audit-verified rather than live. We don't overclaim.",
], size=17)

# 12 errors caught
s = slide("Errors we caught, and how", "Judgment", notes=(
    "This is the 'not slop' slide. Each of these shipped as a bug in some draft and was caught by an audit, "
    "a test or real Excel, then fixed before release."))
errs = [("Roth cap ignored the age-50 catch-up", "phase audit"),
        ("A loss on the shadow portfolio displayed as a green gain", "phase audit"),
        ("Chart palette had fewer colors than categories", "design audit"),
        ("SML sloped down with no explanation", "clicking through the app"),
        ("Excel showed #NAME? on STDEV.S", "recalculating in real Excel"),
        ("One Proof check compared an engine with itself", "final math audit")]
for i, (e, how) in enumerate(errs):
    y = 1.9 + i * 0.78
    text(s, 0.6, y, 8.6, 0.7, e, size=19)
    text(s, 9.3, y + 0.04, 3.6, 0.7, "caught by: " + how, size=14, color=MUTED)

# 13 changed
s = slide("What changed from the plan", "Progress", notes=(
    "Plaid needs API keys, a developer account and bank logins, and email scraping needs inbox access. CSV "
    "export works with any bank, needs no credentials, and keeps data private. Scope grew from a calculator "
    "into a lab, each addition tied to a chapter."))
bullets(s, 0.6, 1.9, 12.2, 4.8, [
    "Plaid and email/Shop Pay scraping became CSV upload: no credentials, any bank, data stays in your session.",
    "Spending + Roth calculator grew into an investments lab: risk, CAPM, diversification, efficiency, uncertainty.",
    "Added a Proof page and an Excel workbook, so a grader can check the math in the course's own tool.",
    "Still true to the plan: runs on other people's real spending, wants vs. needs, invested value, Roth TVM.",
])

# 14 why + limits
s = slide("Why it matters", "So what", notes=(
    "For a person: their own number with a risk range. For the class: theory on real prices, including where "
    "it breaks. For an employer: tested, audited, privacy-safe software and a disciplined way to use AI. "
    "Be upfront about limits."))
bullets(s, 0.6, 1.9, 7.0, 4.8, [
    "Person: \"spend less\" becomes a number with a risk range, from their own data.",
    "Class: CAPM, SML, diversification, efficiency and TVM on real prices, including where theory breaks.",
    "Employer: tested, audited, documented, privacy-safe, and a verified way to use AI.",
], size=18)
text(s, 8.1, 1.9, 4.7, 0.5, "Limitations", size=20, color=PINE, font=SERIF)
bullets(s, 8.1, 2.5, 4.7, 4.2, ["No fees, taxes or spreads.", "Free price data (Yahoo).",
                                 "Short windows are noisy (we say so).", "Roth income limits not checked.",
                                 "A what-if, not advice."], size=15)

# 15 demo
s = slide("Try it", "Live demo", notes=(
    "Open in a full-width window. Click 'Use sample data', then walk: Spending, Shadow, Risk & CAPM (switch to "
    "5 years), Timing, Roth (uncertain returns), Proof (10 of 10, download the workbook)."))
text(s, 0.6, 2.2, 12.2, 1.0, URL, size=24, color=BLUE)
text(s, 0.6, 3.4, 12.2, 2.5, ["Click \"Use sample data\" on the first page.",
                               "Then: Spending, Shadow, Risk & CAPM, Timing test, Roth, Proof.",
                               ("Questions?", {"size": 30, "color": PINE, "font": SERIF})], size=20, spacing=14)

prs.save(f"{OUT}/Spend_Shadow_FIN440.pptx")
print("slides:", len(prs.slides))
