# Spend Shadow: rules for every agent

Spend Shadow is Ashton's FIN 440 Streamlit app: upload a bank CSV, see the spending breakdown,
see what the money would be worth in an index fund (shadow portfolio), and project a Roth IRA.
What each page does, the math conventions and the privacy model are in [README.md](README.md).
Read it before your first change.

## Roles and file ownership
Three agents share this repo. Each one edits only the files it owns.

| Role | Who | Owns |
|---|---|---|
| Builder | Claude Code | `streamlit_app.py`, `app_pages/`, `core/` (except `ui.py`), `tests/`, `sample_data/`, `requirements.txt`, `README.md`, `.gitignore` |
| Designer | Grok | `DESIGN.md`, `.streamlit/config.toml`, `styles.css`, `core/ui.py` |
| Auditor | a fresh Claude Code session | nothing; read-only |
| Shared | all | `HANDOFF.md` (append only), this file (change only when Ashton asks) |

**Claude subagents** (`.claude/agents/`, added at Ashton's request 2026-11-18): `spend-designer` (the Designer row while Grok is out; same files), `spend-auditor` (the Auditor row; read-only tools), `spend-qa` (phone and desktop walkthrough via `tools/walkthrough.py`; no repo edits) and `spend-deck` (the Nov 30 Google Slides deck). Each follows this file.

**Builder:** app logic, data handling, math and tests. Pages call `core/ui.py` for every card,
KPI row and chart, and never style inline (no raw `st.container(border=True)`, `st.metric`
rows or `st.altair_chart` in pages).

**Designer:** the whole look, including Python-level presentation in `core/ui.py`. Keep the
existing function signatures (`section`, `kpi_row`, `chart`) so pages keep working; add new
helpers freely. Before any design work, read `WEB_DESIGN_REFERENCE.md`, fill its section 6
spec into `DESIGN.md`, and run its section 7 checklist before calling a phase done. CSS can
target every block through `.st-key-<key>`; the key list is in README.

**Auditor:** when Ashton says "audit phase N", review that phase's commits and HANDOFF entry in
under 10 bullets: bugs, data leaks, math errors (check TVM and portfolio values by hand, not
by trusting the tests), and whether the UI matches `DESIGN.md`. Report; don't fix.

## Changes across the boundary
Never edit another role's file. Append a request to `HANDOFF.md` instead, addressed to the
owner. Examples: the designer wants sections reordered or a new column on a page (builder
change); the builder needs a new presentation helper (designer change).

## Workflow per phase
1. The owner does the phase's work in its own files.
2. Run `python -m pytest -q`. Everything passes before anything is committed.
3. Commit only your own paths: `git add <paths>`, never `git add .`. Message:
   `<agent>: <what changed>` (agents: claude, grok).
4. Append a HANDOFF entry: phase, what's done, files touched, what the auditor should check.
5. Ashton tells the auditor "audit phase N". The owner gets one fix round, then the phase ships.

All work happens on one feature branch off `master`. No force pushes and no history rewrites.
Push only when Ashton asks.

## Phases
| # | Phase | Owner |
|---|---|---|
| 1 | App logic, math, tests, sample data | Builder (done) |
| 2 | Design system: `DESIGN.md`, `config.toml`, `styles.css`, `ui.py` | Designer |
| 3 | Design pass on each page (layout requests go to the builder via HANDOFF) | Designer + Builder |
| 4 | Polish, deploy, write-up | Builder |
| 5 | Final audit | Auditor team |

**Final audit team (phase 5 only).** The auditor launches three parallel checkers, each a
fresh subagent with its own brief: (a) math: recompute TVM and shadow values by hand from the
sample data; (b) data leaks: anything written to disk, logged, committed or sent off-machine;
(c) design: every page against `DESIGN.md` and the section 7 checklist. The auditor merges the
results into one list of under 10 bullets. Earlier phases use a single auditor; the app is too
small for build teams to pay off.

## Hard rules
- **No real financial data in git.** `.gitignore` blocks every `*.csv` except
  `sample_data/sample_transactions.csv`, which is fictional. Real files go in `data/`
  (gitignored).
- Uploads live only in `st.session_state`. Nothing writes transaction data to disk or logs.
  The only outbound request is a ticker and a start date to Yahoo Finance.
- No secrets, keys or account numbers in any file.
- No em dashes in anything you write. Use commas, colons or parentheses.
