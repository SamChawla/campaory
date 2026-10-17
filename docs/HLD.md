# Campaory: High-Level Design (HLD)

Version 1.1, 16 Oct 2026. Read with [ARCHITECTURE](ARCHITECTURE.md) (diagrams) and [LLD](LLD.md) (details).

## 1. Context and constraints

- One developer, about 2.5 days of build and test, hard deadline 19 Oct 12:29 PM IST.
- Free or low-cost hosting: Render web service plus Render Postgres.
- Open-weight model (Gemma) must do the language work.
- Guest mode must be real: no server storage of guest campaigns.

## 2. Logical components

| Component | Responsibility | Tech |
|---|---|---|
| SPA | UI, guest state, localStorage persistence, API calls | React 18, Vite, TS, Zustand, React Router |
| API | HTTP surface, validation, auth, rate limiting | FastAPI, Pydantic v2 |
| Domain | Facts rules, planning dates, platform validators, guard, impact | Pure Python |
| LLM adapter | One interface for Gemma 4 via Euri and the mock | httpx |
| Page fetcher | SSRF-safe URL fetch and text extraction | httpx, selectolax or BeautifulSoup |
| Auth | Google OAuth, session cookie | Authlib, itsdangerous |
| Persistence | Users and saved campaigns | SQLAlchemy 2, Alembic, Postgres |
| Observability | Logs, optional Sentry spans | structlog or logging, sentry-sdk |

## 3. Data flow summary

1. Guest: SPA holds the campaign document. Each AI step posts the needed slice to a stateless endpoint and merges the response into the document.
2. Save: SPA authenticates, then posts the whole document once. The server stores it relationally (see LLD section 4).
3. Signed-in editing: SPA PUTs the full document with `version`; server replaces the campaign tree in one transaction. Optimistic lock prevents lost updates across tabs.

Why full-replace PUT: the document is small (tens of KB), it avoids a large patch API, and it keeps the guest and signed-in code paths identical.

## 4. Modes

| Aspect | Guest | Signed in |
|---|---|---|
| Source of truth | localStorage `campaory.guest.v1` | Postgres |
| AI endpoints | Same endpoints, guest limits | Same endpoints, higher limits |
| Save | Prompts sign-in | Autosave, 1.5 s debounce |
| Multiple campaigns | One | Free plan: one saved campaign (see 9) |

## 5. Key technical decisions

See ADRs 001 to 008. In short: FastAPI + React on one Render service; Gemma behind an adapter; guest stateless API; Google OAuth with a cookie session; deterministic guard; change impact by `facts_used`; copy-and-open; in-memory rate limiting.

## 6. External dependencies and failure behaviour

| Dependency | Failure | Behaviour |
|---|---|---|
| Gemma API | timeout, 5xx, quota | One retry with backoff, then `502 llm_unavailable` with retry option; campaign document untouched; if `LLM_FALLBACK_TO_MOCK` then mock with badge |
| Event page | blocked, 4xx, too large, SSRF | `422 fetch_failed` with reason; offer paste-text path |
| Google OAuth | denied, misconfigured | Return to app with `?auth=failed`; guest work untouched |
| Postgres | down | Signed-in endpoints 503; guest endpoints keep working |
| Sentry | down | Ignored |

## 7. Performance and capacity

- Expected load: tens of users during judging. Single instance, 1 uvicorn worker with async handlers is enough.
- Model calls are the latency. Generate posts in batches by plan item (one model call per item with four platform variants, 3 in parallel) and stream progress via sequential client requests, not server push.
- Render free tier sleeps. Mitigation: hit `/api/health` from an uptime pinger before demos. Paid starter instance removes this if budget allows.

## 8. Security and privacy

| Threat | Control |
|---|---|
| SSRF through URL fetch | http/https only, DNS resolve then block private, loopback, link-local, metadata ranges; re-check on redirects (max 3); 5 s timeout; 1 MB cap |
| Prompt injection from fetched pages | Page text is passed as data inside delimiters with an instruction to ignore instructions in it; output is schema-validated; the guard blocks unknown facts; the model has no tools |
| XSS | React escaping; no `dangerouslySetInnerHTML`; strict CSP header |
| CSRF | SameSite=Lax cookie, JSON-only, `X-Requested-With` header on mutating calls |
| Account data access | Every query filters by `user_id`; foreign ids return 404 (BR12) |
| Secrets | Env vars on Render; never in repo; `.env.example` only |
| Abuse | Rate limits and daily cap (ADR-008), body size limits |
| PII | Store only provider, subject, email, name, avatar; delete account cascades |
| Logs | Do not log campaign text or tokens; log ids, sizes, timings |

Privacy statement for the UI: guest text is sent to the model provider to generate posts; Campaory does not store it unless you sign in and save.

## 9. Scaling path (not built)

- Replace in-memory limiter with Postgres or Redis counters.
- Move model calls to a queue if latency grows.
- Add direct publishing adapters behind the same post model.
- Free plan limit of one saved campaign: enforced server-side in `POST /api/campaigns` (409 `campaign_limit`). This is a product assumption from the BRD pricing table; confirm before enforcing.

## 10. Environments

| Env | Model | DB | Notes |
|---|---|---|---|
| Local dev | mock (default) or gemma with key | SQLite file | `make dev` runs API and Vite |
| Tests | mock | SQLite in memory | No network |
| Production | gemma, fallback mock optional | Render Postgres | Sentry optional |

## 11. Observability

- Request log line: method, path, status, duration, user or guest id hash.
- LLM call log: task, provider, model, prompt version, latency, input and output tokens, outcome.
- Sentry (optional): span per LLM call with the same attributes; capture exceptions. Only claim Sentry Agent Tracing in the submission if traces are real.
