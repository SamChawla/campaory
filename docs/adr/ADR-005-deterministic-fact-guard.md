# ADR-005: Deterministic fact guard around every LLM output

Status: Accepted. Date: 2026-10-16. Source: BRD BR01, BR02, FR 11, section 11.1 (AI safeguards).

## Context
The product's promise is that posts do not invent event details. Prompting alone cannot guarantee that. Small and mid-size models drift on dates, times and links.

## Decision
Code, not the model, owns facts and constraints.

1. Prompts receive only confirmed facts (BR01). Unconfirmed facts are not sent.
2. The model returns structured JSON including `facts_used` (fact keys).
3. After every generation or redraft, `domain/guard.py` extracts from the text: URLs, dates, times, currency amounts, @handles, and numeric counts. Each extracted token must match a confirmed fact value (after normalisation) or be a user-approved free text. Otherwise the post is flagged `needs_review` with a reason code (`UNKNOWN_URL`, `UNKNOWN_DATE`, `UNKNOWN_TIME`, `UNKNOWN_AMOUNT`, `UNKNOWN_HANDLE`).
4. Missing facts become explicit placeholders `[ADD: speaker name]`. A post with any placeholder cannot be approved (BR02).
5. Platform limits (X 280 with links counted as 23, LinkedIn 3000, Instagram 2200 and at most 30 hashtags, WhatsApp about 700) are checked in code; the model is told the limits but is not trusted (FR 11).
6. Dates in the plan (reminder, last-call, day-of) are computed by `domain/planning.py` from the event date. The model writes copy only.
7. The guard result is stored on the post (`guard_flags`) and shown in the UI next to the post.

## Consequences
- False positives happen (a legitimate year such as "2026" in running text). The guard allows years and ordinals that appear in confirmed facts, and shows the reason so the user can override by editing the fact or the text. Override means the user edits the post, and the guard re-runs on the edited text.
- Regex extraction is imperfect for non-English dates. The MVP is English-first. State this in the README.
- This is the most valuable test surface in the project. The golden tests live in `tests/domain/test_guard.py`.

## Alternatives considered
- Ask a second LLM to judge: slower, non-deterministic, and still not trustworthy for exact strings.
- Trust prompt instructions only: fails the core promise.
