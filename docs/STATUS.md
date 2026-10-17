# Status

Updated 17 Oct 2026, evening IST. 530 backend tests, 75 frontend unit tests, 4 Playwright runs (golden path and save flow at 360 and 1280 px) pass.

| Milestone | State | Notes |
|---|---|---|
| M0 Skeleton + deploy | Local done; T0.5 open | Health, error shape, SPA fallback, Docker image verified locally. Render deploy needs the account. Alembic step is back in the Dockerfile start command |
| M1 Domain core | Done | schemas, facts (BR01 gate + tokeniser), planning, platforms, guard, impact, textdiff, posts. 209 backend tests |
| M2 AI layer + API | Done (T2.3 replaced by Euri) | `call_validated` + JSON repair, versioned prompts, mock provider, provider factory with labelled mock fallback, SSRF-safe fetch + HTML text, token-bucket limits + daily cap, `/brief/extract`, `/plan/propose`, `/posts/generate|revise|validate`, `/impact/analyze|redraft`, `/config`, security headers, body caps, `X-Requested-With` check. Gemma and Ollama providers removed (ADR-002 note) |
| M3 Frontend guest flow | Done | Start (link, text, sample), Facts, Plan, Posts, Changes, Upcoming, guest banner, Demo model badge, limit and error states. Playwright golden path passes against the mock backend. Live run against Euri: extract 15 to 19 s, generate one item for four platforms 10 to 15 s, all posts pass the guard |
| M4 Auth + save | Done except T4.8 (production OAuth client) | Models + Alembic `0001_init` (runs on start in Docker), repo, signed session cookie, Google OAuth, `/me`, saved-campaign CRUD. Test-only login at `POST /api/auth/test-login` when `APP_ENV=test`. Frontend: sign-in sheet, save import after `/?auth=ok`, `/saved`, `/c/:id/*`, sign out, delete account; save flow e2e passes. Needs the Google OAuth client (DEPLOYMENT 2) for a manual login check |
| M5 to M6 | Not started | |

## Decisions made while building
- Planning: `today` means the start of that day in the event timezone; the speaker/mentor/judge intro item is left out when there are no people (no placeholder item). LLD 6.1 updated.
- Guard: amounts of zero are always allowed ("free", "₹0"); tokens inside text that repeats a confirmed fact verbatim (address, venue, event name) are allowed; counts are allowed when the number appears in a confirmed fact or equals the length of a people list.
- Whatsapp counter shows 700 as the limit (soft); 4096 is the hard error.

- DB: list columns are JSON (not Postgres arrays) so one schema runs on SQLite and Postgres. Server row ids are internal; documents keep their browser ids, so two accounts can save the same document. Timestamps come back in UTC (`Z`), same instant.
- Session cookie lifetime is 30 days (ADR-004 updated from 14).

## Needs the owner
- Render deploy (T0.5): blueprint is ready; set `EURI_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `BASE_URL`. The Docker image has not been built locally yet (Docker Desktop was not running)
- Google OAuth client with both redirect URIs (DEPLOYMENT 2), then a manual login on localhost
- Three organizer names for trials (M6)
- M2: guest model limits use IP plus the `cid` cookie, plus a per-IP bucket at 3x so a rotating cookie cannot bypass them. Signed-in users are keyed by user id. Body cap is 256 KB except `/api/campaigns` (document cap plus 16 KB). The sample extraction returns `meta.provider = "none"`. Daily cap reached without fallback is 503 `llm_unavailable` (ADR-008).
