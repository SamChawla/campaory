# Campaory

Facts first. Then posts.

Campaory turns one verified event brief into a coordinated campaign for LinkedIn, Instagram, WhatsApp and X. You confirm the facts; code checks every date, time and link; a Gemma model writes the copy. Try it without an account. Sign in only to save.

Status: documentation pack only. No application code yet.

## Start here
1. `docs/HANDOFF.md`: setup, accounts, decisions, risks
2. `docs/IMPLEMENTATION_PLAN.md`: task list with acceptance criteria
3. `CLAUDE.md`: rules for Claude Code in this repo

## Documents
| Document | Purpose |
|---|---|
| `docs/Campaory_Business_Requirements_Document_v1.1.docx` | Business requirements (current). `docs/Campaory_BRD_v1.0_original.docx` is the earlier version |
| `docs/PRD.md` | Product requirements, stories, acceptance |
| `docs/DESIGN.md` | Design overview and scope cut |
| `docs/UI_SPEC.md`, `docs/mockups/` | Visual design, tokens, mockup sources, unmocked screens |
| `docs/ARCHITECTURE.md` | Diagrams (Mermaid) |
| `docs/HLD.md`, `docs/LLD.md` | High-level and low-level design, API, schema, algorithms |
| `docs/adr/` | Eight architecture decision records |
| `docs/TEST_PLAN.md`, `docs/DEPLOYMENT.md` | Testing and Render setup |
| `docs/SUBMISSION.md` | DEV submission kit |

## Planned stack
FastAPI, React (Vite), PostgreSQL on Render; Gemma through a provider adapter; Google sign-in.

## Licence
MIT (add `LICENSE` before publishing).
