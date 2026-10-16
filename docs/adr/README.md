# Architecture Decision Records

Format: Context, Decision, Consequences, Alternatives. Status is Accepted unless stated.

| ADR | Title | Status |
|---|---|---|
| [001](ADR-001-stack-and-single-service.md) | FastAPI + React (Vite) + PostgreSQL as one Render service | Accepted |
| [002](ADR-002-llm-provider-adapter.md) | Gemma behind a provider adapter, with mock and Ollama | Accepted |
| [003](ADR-003-guest-first-stateless-api.md) | Guest-first: stateless API, browser persistence | Accepted |
| [004](ADR-004-auth-oauth-session-cookie.md) | Sign-in with Google OAuth and a server session cookie | Accepted, confirm provider |
| [005](ADR-005-deterministic-fact-guard.md) | Deterministic fact guard around every LLM output | Accepted |
| [006](ADR-006-change-impact-by-facts-used.md) | Change impact from `facts_used` plus text scan | Accepted |
| [007](ADR-007-copy-and-open-no-publishing.md) | Copy and open the platform; no direct publishing | Accepted |
| [008](ADR-008-rate-limits-and-cost-control.md) | In-memory rate limits and a daily cap | Accepted, revisit when scaling |
