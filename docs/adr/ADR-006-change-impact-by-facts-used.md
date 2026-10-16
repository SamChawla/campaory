# ADR-006: Change impact from `facts_used` plus text scan

Status: Accepted. Date: 2026-10-16. Source: BRD FR 16, FR 17, FR 18, BR03, BR04.

## Context
When an organizer changes a fact (time, venue, price), they need to know which posts are now wrong, without the tool rewriting posts that are already public.

## Decision
- A post is affected if its `facts_used` contains the changed fact key, or if its text still contains the old fact value after normalisation (catches facts the model used but did not list).
- Posts with status `published` are never rewritten (BR03). They are listed as "already public" with a suggested correction note the user can post separately.
- Affected unpublished posts move to `needs_review` and keep their current text until the user accepts a proposal (BR04).
- Redrafts are proposals: the server returns `{post_id, proposed_text, changed_spans, reason}`. The client shows a diff. Accept replaces text and re-runs the guard. Keep current leaves the post in `needs_review` until approved again.
- Redrafts send the model the old text, the changed fact (old and new) and the confirmed fact set, and ask for the minimum edit.
- Maximum 3 redrafts in parallel from the client to respect rate limits.

## Consequences
- Deterministic first, model second: the impact list is correct even if the model is down.
- Normalisation (dates, times, currency) is shared with the guard, one implementation.
- A fact referenced only implicitly ("this Saturday") is not found by text scan. The plan item date change also marks posts attached to that plan item as affected.

## Alternatives considered
- Regenerate all posts on any change: destroys user edits and violates BR04.
- Ask the model which posts are affected: unreliable and slower.
