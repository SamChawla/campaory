# Campaory: Handoff for VS Code

How to pick this up and keep going. Written 16 Oct 2026 from a cloud session; nothing here has been run against real accounts yet.

## 1. What exists and what does not

Exists: BRD v1.1, this doc pack, six mockup sources, design tokens, `render.yaml`, `Dockerfile`, `.env.example`, `Makefile`, a sample event text.
Does not exist: any application code, tests, migrations, accounts, keys, deployment.

## 2. First 30 minutes

1. Install: Python 3.12, Node 22, Git, Docker (optional locally), VS Code.
2. VS Code extensions: Python, Pylance, Ruff, ESLint, Prettier, Markdown Preview Mermaid Support, Playwright Test, Docker (optional), Claude Code.
3. Unzip the pack, `git init`, first commit "docs: initial doc pack".
4. Read in this order: BRD v1.1 → PRD → DESIGN → ARCHITECTURE → LLD → IMPLEMENTATION_PLAN. About 45 minutes. Skim the ADRs.
5. Open Claude Code in the repo root. `CLAUDE.md` tells it the rules and the pipeline.
6. Start at T0.1 in the implementation plan.

Suggested first prompt for Claude Code:
"Read CLAUDE.md and docs/IMPLEMENTATION_PLAN.md. Do T0.1 to T0.4. Follow TDD. Stop after T0.4 and show me the results."

## 3. Accounts and keys (do these on day 1)

| Item | Why | Time | Notes |
|---|---|---|---|
| GitHub repo (public) | Submission requires a public repo | 5 min | Add MIT licence |
| Euri API key | Gemma 4 | have | Model check done, see below |
| Render account | Hosting | 10 min | Connect GitHub |
| Google Cloud OAuth client | Login | 30 min | See DEPLOYMENT 2; unverified-app screen is likely |
| `.tech` promo claim | Domain category | 15 min | hacktoberfest.com/my/promos; verify the deadline |
| Sentry account (optional) | Agent Tracing category | 15 min | Only if you will really use it |
| DEV account | Submission | have | |

### Gemma model check

Done on 17 Oct 2026 against Euri (`google/gemma-4-26B-A4B-it`). Results in `docs/MODEL_NOTES.md`. Google AI Studio and Ollama were dropped (ADR-002 note).

## 4. Decision log (from the planning conversation)

| Date | Decision | Why |
|---|---|---|
| 16 Oct | New project started in the challenge window (Campaory) | Rules require a project started within 12 to 18 Oct |
| 16 Oct | Gemma via hosted API behind an adapter, mock for tests and demo fallback | No GPU hosting in time; keep the open-model story honest |
| 16 Oct | FastAPI + React (Vite) + Postgres, one Render service | Developer strength in Python; interactive UI needs React |
| 16 Oct | Scope cut: no poster OCR, no Hindi/Hinglish guarantees, no brand voice | Time; listed as roadmap |
| 16 Oct | UI direction: wide heavy type, pill nav, forest/lime/coral, motion; not "AI-looking" | User feedback on first two drafts |
| 16 Oct | Guest-first: full flow without login; login only to save | User requirement; BRD v1.1 |
| 16 Oct | Google login first, GitHub only if time | Fewest setup steps |

## 5. Open questions and risks (be honest with yourself)

1. Auth + save is the schedule risk. If M4 slips past 18 Oct noon, ship guest-only plus "Save to file (JSON export)" as a fallback and say so in the article. Do not ship half-working login.
2. Gemma availability and JSON quality is unverified. See section 3.
3. The guard will have false positives on real pages; tune with real text.
4. Three real organizers: you need names today. Without real trials the "My First User" story and the user-testing claims in the BRD are not true. Do not write them unless they are.
5. BRD pricing is indicative, not validated. Do not present it as market evidence.
6. Sentry and Entire categories are only worth claiming with real evidence (traces, session logs). If you do not use them, drop the claim.
7. `render.yaml` and OAuth steps were written without access to those consoles; expect small corrections.
8. Sign-in, save and error screens are not mocked. They follow UI_SPEC 7.
9. Hindi and Hinglish are P1; do not promise them.
10. The BRD should get a v1.2 noting guard-blocks-approval and the free-plan one-campaign limit (assumption).

## 6. Working agreement with Claude Code

- Use the 7-phase pipeline from your preferences, scaled to the task: for a one-file change skip the ceremony.
- Tests first for domain, LLM wrapper, fetch and API code.
- Subagents for independent tasks (M1 domain modules; M3 screens); the orchestrator coordinates and does not write production code.
- 3-strike rule when debugging.
- After each milestone, update `docs/IMPLEMENTATION_PLAN.md` status column or add a `STATUS.md` with what is done.

## 7. Daily checklist

- Start: pull, run tests, read the plan task.
- During: commit per task, deploy per milestone.
- End: update status, note blockers, push.

## 8. Contact points in the docs

| Question | Read |
|---|---|
| What does "approved" require? | LLD 7, BRD BR02 |
| How are dates computed? | LLD 6.1 |
| Why can't the guard allow X? | ADR-005, LLD 6.2 |
| What is the import format? | LLD 3, ADR-003 |
| How do I configure Render? | DEPLOYMENT |
| What does the DEV post need? | SUBMISSION |
