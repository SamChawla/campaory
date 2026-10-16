# Campaory: Test plan

Version 1.1. Strategy: most logic is deterministic and unit-tested; the model is replaced by the mock provider in all automated tests; Gemma is checked by a smoke script and by manual trials.

## 1. Levels

| Level | Tool | Scope |
|---|---|---|
| Unit | pytest | `domain/`, `llm/` wrapper, `fetch/`, `core/` |
| API | pytest + httpx AsyncClient, SQLite | every endpoint, error shapes, auth, ownership |
| Frontend unit | Vitest + Testing Library | store, storage, share URLs, components |
| End to end | Playwright (Chromium) at 360x800 and 1280x800 | golden paths against the mock provider |
| Manual | checklist below | real Gemma, real Google login, phone, 3 organizers |

## 2. Traceability to BRD acceptance criteria

| BRD scenario | Test |
|---|---|
| Create from URL | `test_brief.py::test_url_happy` (mocked fetch), manual with the real PyData page |
| Create from text | `test_brief.py::test_text_happy`; e2e golden |
| Generate plan | `test_planning.py` (6 cases) |
| Generate variants | `test_posts_generate.py::test_four_platforms_distinct` |
| Revise content | `test_posts_revise.py`; e2e checks previous version recoverable |
| Copy and redirect | Vitest `share.test.ts` (URL encoding); e2e asserts clipboard content |
| Schedule reminder | `test_posts_rules.py::test_schedule_needs_future_and_approved` |
| Update event fact | `test_impact.py`; e2e change-fact scenario |
| Protect published post | `test_impact.py::test_published_never_modified`; `test_impact_api.py::test_redraft_published_409` |
| Mobile flow | e2e at 360 px asserts `scrollWidth <= clientWidth` on every screen |
| Try without signing in | e2e golden asserts no request to `/api/auth/*` and no sign-in dialog |
| Guest work survives a reload | e2e reloads at each step |
| Save requires sign-in | `e2e/save.spec.ts` with fake login; `test_campaigns.py::test_import_idempotent` |
| Request limits | `test_rate_limit.py`, `test_api_limits.py`; e2e checks banner and that doc is intact |
| Private by default | `test_campaigns.py::test_other_user_404` for GET, PUT, DELETE |

## 3. Critical unit cases

Guard (`test_guard.py`): wrong date; wrong time; wrong URL; extra UTM param on the right URL passes; price not in facts; handle not in facts; "free" allowed; relative date info; placeholder; right post passes; year-only mention; Indian date format `17/10/2026`; `17th Oct`; 12-hour vs 24-hour times equal; en dash time ranges.

Platforms: X exactly 280 passes, 281 fails, URL counts 23; Instagram 30 hashtags passes, 31 fails; LinkedIn 3000/3001; WhatsApp warning over 700.

Plan: event in 30, 9, 3, 1 days; event today (only event-day + post items); multi-day event; registration deadline earlier than start; no speakers.

SSRF (`test_safe_fetch.py`): `http://127.0.0.1`, `http://localhost`, `http://[::1]`, `http://169.254.169.254`, `http://10.0.0.1`, decimal and hex IP forms, DNS name resolving to private (mock resolver), redirect to private, `file://`, `ftp://`, oversize body, slow response.

LLM wrapper: invalid JSON then valid repair; invalid twice; prose around JSON; timeout; 429 from provider mapped to `llm_unavailable`.

Rate limit: bucket refill, per-key isolation, daily cap with mock fallback on and off.

Auth: tampered cookie; expired cookie; POST without `X-Requested-With`; OAuth `state` mismatch; open redirect attempt in `next` ignored.

Import: same `client_id` twice → one row; doc with unknown fields rejected; doc over 512 KB rejected; version conflict; deep-equal round trip (doc in = doc out apart from `version` and timestamps).

## 4. End-to-end scenarios (Playwright)

1. `golden.spec.ts`: sample event → confirm all facts → generate plan → generate posts → approve one post per platform → copy (assert clipboard) → edit start time → see 2+ affected posts → accept a redraft → published post (mark one published first) unchanged → reload → state identical.
2. `blocked.spec.ts`: leave audience unconfirmed → "Generate plan" disabled with message naming audience.
3. `limits.spec.ts`: force 429 → banner with countdown → doc intact.
4. `save.spec.ts`: guest work → Save → fake login → doc appears at `/c/{id}` equal to before → local key cleared → second user cannot open it.
5. `mobile.spec.ts`: 360 px run of scenario 1; asserts no horizontal scroll and 44 px targets on primary actions.
6. `storage.spec.ts`: storage disabled → banner; corrupted JSON → backup key created, app usable.

## 5. Manual checklist (before submit)

- [ ] Gemma smoke: extraction on PyData page; 4 posts for 3 items; guard flags at most a few false positives
- [ ] Real Google login on the Render URL and on the .tech domain, in a private window
- [ ] Phone (real device, mobile data): guest flow to copy; open WhatsApp share
- [ ] Cold start: first request after idle works (loading state shown)
- [ ] Rate limit message visible and readable
- [ ] Deleting a campaign removes it; second account cannot see it
- [ ] README setup steps work on a clean clone (`make setup && make dev`)
- [ ] No secrets in git history (`git log -p | grep -i key` and a secret scanner)
- [ ] Security headers present (CSP, X-Content-Type-Options, Referrer-Policy)
- [ ] Prompt-injection fixture page does not produce unconfirmed facts

## 6. Model quality evaluation (small, honest)

Make a table of 10 real event pages or texts (include your own events). For each, record: facts extracted correctly / total, facts hallucinated, posts passing guard first time, posts needing edits, and whether you would post it. Report real numbers in the article, including failures. Do not claim percentages from fewer than 10 cases.

## 7. Exit criteria

All automated tests green in CI; manual checklist complete; BRD section 22 release criteria met; known defects listed in README "Limitations".
