# Plan (owned by the project lead, Claude Code)

The lead writes this plan; each agent does only its own tasks; the lead updates the status
column. Requests between agents still go through HANDOFF.md. Last updated 2026-11-18.

## Who audits what
- **Grok** audits the builder's phases (1, 3B, 4), when Ashton says "audit phase N".
- **Grok's own phases** (2, 3D) are audited by a fresh Claude subagent the lead launches, so no
  agent grades its own work.
- **Phase 5** is the 3-checker final audit team in AGENTS.md.

## Phase status
| Phase | State |
|---|---|
| 1 Logic, math, tests | Done, audited, fix round committed (`b21c92c`) |
| 2 Design system | Done by Grok (`8f9e98a`); audited, fix round with Grok (HANDOFF) |
| 3 Design pass on pages | **Active** |
| 4 Polish, deploy, write-up | Next |
| 5 Final audit | Last |

## Phase 3: design pass
| ID | Owner | Task | Done when | Status |
|---|---|---|---|---|
| 3B.1 | Builder | Upload: page link + Clear data in a horizontal row (Grok request) | Both sit on one row at desktop width | done |
| 3B.2 | Builder | Roth: delta on the Growth KPI so it reads green | Growth shows "+N% on contributions" | done |
| 3B.3 | Builder | Shadow/Roth chart colors (Grok request) | Already handled inside `ui.chart`; no page change | closed |
| 3D.1 | Grok | Run the app, check each page at 1280px and 390px against DESIGN.md, file any layout change as a HANDOFF request | One HANDOFF entry per page, or "no changes" | todo |
| 3D.2 | Grok | Record the WEB_DESIGN_REFERENCE section 7 checklist results in DESIGN.md | Every box answered yes/no with a note | todo |
| 3A | Lead | Fresh subagent audits phase 2 + 3D; Grok audits 3B | Findings fixed in one round | phase 2 audit done; Grok fixing; 3D audit later |
| 3D.3 | Grok | Phase 2 audit fixes (HANDOFF): palette size, series domain, Clear button color, CSS nits, contrast | Each item done or answered in HANDOFF | todo |

## Phase 4: polish, deploy, write-up (builder, run as a small team)
The lead runs three workers in parallel, then reviews and commits. They touch separate files;
README edits merge through the lead.
| ID | Worker | Task | Done when | Status |
|---|---|---|---|---|
| 4.1 | Robustness | Audit item 7: the amount auto-detect must skip date-like columns; tighten the `lime` / `metro` / `toll` keywords; tests for each. Audit item 9: fix the README note about which test needs network. | New tests pass | done (`0f69b4c`), item 9 done |
| 4.2 | Deploy | Make the repo ready for Streamlit Community Cloud: pinned requirements, no local paths, a deploy section in README | `streamlit run` works from a clean venv | done: pinned, 35 tests + smoke pass in a clean venv, DEPLOY.md |
| 4.3 | Write-up | Draft the FIN 440 write-up from README + HANDOFF (method, TVM math, sample results, limits) | Matches the rubric | **blocked: needs rubric** |

## Needs Ashton
1. **FIN 440 rubric and due date** for the write-up (4.3). Nothing in the Brain has them.
2. **Deploy (steps in DEPLOY.md):** a GitHub repo (public or private) and your Streamlit Community Cloud sign-in.
   Agents can't create accounts for you.
3. Say "audit phase N" to Grok when a builder phase lands.
