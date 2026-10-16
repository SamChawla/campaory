# Status

Updated 16 Oct 2026, evening IST.

| Milestone | State | Notes |
|---|---|---|
| M0 Skeleton + deploy | Local done; T0.5 open | Health, error shape, SPA fallback, Docker image verified locally. Render deploy needs the account. Alembic step returns to the Dockerfile with T4.1 |
| M1 Domain core | Done | schemas, facts (BR01 gate + tokeniser), planning, platforms, guard, impact, textdiff, posts. 209 backend tests |
| M2 AI layer + API | Not started | Run the Gemma model check (HANDOFF 3) before T2.3 |
| M3 to M6 | Not started | |

## Decisions made while building
- Planning: `today` means the start of that day in the event timezone; the speaker/mentor/judge intro item is left out when there are no people (no placeholder item). LLD 6.1 updated.
- Guard: amounts of zero are always allowed ("free", "₹0"); tokens inside text that repeats a confirmed fact verbatim (address, venue, event name) are allowed; counts are allowed when the number appears in a confirmed fact or equals the length of a people list.
- Whatsapp counter shows 700 as the limit (soft); 4096 is the hard error.

## Needs the owner
- Render account and blueprint deploy (T0.5)
- Google AI Studio key and the Gemma model check, written to `docs/MODEL_NOTES.md`
- Three organizer names for trials (M6)
