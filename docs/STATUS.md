# Status

Updated 16 Oct 2026, evening IST.

| Milestone | State | Notes |
|---|---|---|
| M0 Skeleton + deploy | Local done; T0.5 open | Health, error shape, SPA fallback, Docker image verified locally. Render deploy needs the account. Alembic step is back in the Dockerfile start command |
| M1 Domain core | Done | schemas, facts (BR01 gate + tokeniser), planning, platforms, guard, impact, textdiff, posts. 209 backend tests |
| M2 AI layer + API | Not started | Run the Gemma model check (HANDOFF 3) before T2.3 |
| M3 | Not started | |
| M4 Auth + save | Backend done (T4.1 to T4.5); T4.6 to T4.8 open | Models + Alembic `0001_init` (runs on start in Docker), repo, signed session cookie, Google OAuth, `/me`, saved-campaign CRUD. Test-only login at `POST /api/auth/test-login` when `APP_ENV=test`. Needs the Google OAuth client (DEPLOYMENT 2) for a manual login check |
| M5 to M6 | Not started | |

## Decisions made while building
- Planning: `today` means the start of that day in the event timezone; the speaker/mentor/judge intro item is left out when there are no people (no placeholder item). LLD 6.1 updated.
- Guard: amounts of zero are always allowed ("free", "₹0"); tokens inside text that repeats a confirmed fact verbatim (address, venue, event name) are allowed; counts are allowed when the number appears in a confirmed fact or equals the length of a people list.
- Whatsapp counter shows 700 as the limit (soft); 4096 is the hard error.

- DB: list columns are JSON (not Postgres arrays) so one schema runs on SQLite and Postgres. Server row ids are internal; documents keep their browser ids, so two accounts can save the same document. Timestamps come back in UTC (`Z`), same instant.
- Session cookie lifetime is 30 days (ADR-004 updated from 14).

## Needs the owner
- Render account and blueprint deploy (T0.5)
- Google OAuth client with both redirect URIs (DEPLOYMENT 2), then a manual login on localhost
- Google AI Studio key and the Gemma model check, written to `docs/MODEL_NOTES.md`
- Three organizer names for trials (M6)
