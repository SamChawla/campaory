# CLAUDE.md: Campaory

Campaory turns one verified event brief into a campaign for LinkedIn, Instagram, WhatsApp and X. Guests can use everything; signing in is only needed to save. Facts are confirmed by the human, code enforces them, the model only writes copy.

## Read first
`docs/Campaory_Business_Requirements_Document_v1.1.docx` → `docs/PRD.md` → `docs/DESIGN.md` → `docs/LLD.md` → `docs/IMPLEMENTATION_PLAN.md`. ADRs in `docs/adr/`. UI in `docs/UI_SPEC.md` and `docs/mockups/`.

## Stack
Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx, Authlib. Frontend: React 18, Vite, TypeScript, Zustand, plain CSS with `tokens.css`. DB: Postgres (prod), SQLite (dev/test). Deploy: one Docker service on Render.

## Commands
```
make setup     # create venv, install backend and frontend deps
make dev       # API on :8000, Vite on :5173 (proxy /api)
make test      # backend pytest + frontend vitest
make e2e       # Playwright against mock provider
make lint
```

## Non-negotiable rules
1. Tests first for `domain/`, `llm/`, `fetch/`, `api/`, `core/`. No production code without a failing test.
2. `domain/` has no I/O and no framework imports.
3. The LLM never decides dates, limits, links, statuses. Only `llm/` imports a model client.
4. Only confirmed facts reach a prompt. Every generated post goes through `domain/guard.py` and `domain/platforms.py`.
5. Published posts are never modified (BR03). Opening a platform never marks published (BR05).
6. Guest data is never stored on the server. Do not add server persistence to stateless endpoints.
7. Every saved-campaign query filters by `user_id`; foreign ids return 404 (BR12).
8. Never log campaign text, tokens or secrets.
9. Default `LLM_PROVIDER=mock` in tests and local dev. Any mock output shown to users carries the "Demo model" badge.
10. No TODO/placeholder code. If a thing is out of scope, it is not in the code.
11. Keep `docs/LLD.md` in sync with endpoints and schemas whenever you change them.

## Working style
- User prefers direct, honest feedback. Say when something is a bad idea.
- Follow the 7-phase pipeline scaled to the task size: brainstorm (one question at a time) → plan → execute with subagents → TDD → two-stage review → systematic debugging (3-strike rule) → ship. Quick fixes skip the ceremony.
- Commit small. Conventional commit messages.

## Where things are
Endpoints: LLD section 5. Document shape: LLD section 3. Rules: BRD section 13 and LLD section 7. Env vars: LLD section 2 and `.env.example`.

## Deadline
Submission by 19 Oct 2026, 09:00 IST (hard limit 12:29 PM IST). Guest flow must be shippable before auth work starts.
