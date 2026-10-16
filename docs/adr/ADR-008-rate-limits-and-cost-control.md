# ADR-008: In-memory rate limits and a daily cap

Status: Accepted, revisit when scaling. Date: 2026-10-16. Source: BRD FR 26, section 12 (Abuse control).

## Context
Guests can call model-backed endpoints without an account. A public demo with a free API key will be abused or exhausted, and a quota error in front of a judge is the worst failure.

## Decision
- A token-bucket limiter in `core/rate_limit.py`, in process memory, keyed by:
  - guests: client IP (first value of `X-Forwarded-For` set by Render's proxy, validated) plus a random `cid` cookie
  - signed-in users: user id
- Default limits (env-configurable): guests 10 model calls per hour and 30 per day; users 40 per hour; global daily cap `LLM_DAILY_CAP=500` calls.
- When a limit is hit the API returns 429 with `{error: "rate_limited", retry_after_seconds}`. The UI explains it and suggests signing in (higher limit) or waiting.
- When the global cap is hit and `LLM_FALLBACK_TO_MOCK=true`, return mock output with the visible "Demo model" badge (see ADR-002). Otherwise return 503 `llm_unavailable`.
- Non-model endpoints (validate, impact analyze, plan propose) are not model-limited, but have a generous per-IP request limit (120/min).
- Max request body 256 KB. Max fetched page size 1 MB. Max text sent to the model 20k characters, truncated with a notice.

## Consequences
- Simple and enough for one instance. State resets on deploy and restart.
- With more than one instance the limits multiply. Move to Redis or a Postgres counter then.
- IP-based limits are weak behind shared networks and trivial to evade; the global daily cap is the real protection.
- Unauthenticated users can burn the daily cap. Accepted for the demo; mitigation is the lower guest limit.

## Alternatives considered
- Redis: another service to run for a one-instance app.
- Cloudflare or Render-level limits: not in free plan scope.
- Require login for all model calls: contradicts the guest-first requirement.
