# ADR-003: Guest-first: stateless API, browser persistence

Status: Accepted. Date: 2026-10-16. Source: BRD v1.1, FR 21 to FR 24, BR 09 to BR 11.

## Context
A visitor must be able to try the whole workflow with no account. Saving needs sign-in. We do not want to store anonymous data on the server (privacy, cost, abuse surface).

## Decision
- The campaign is one JSON document (see LLD section 3). The same shape is used in localStorage and in the API.
- Guest mode: every AI and rule endpoint is stateless. The client sends the facts and posts it needs; the server computes and returns, and stores nothing.
- The guest campaign is persisted in localStorage under `campaory.guest.v1` with a schema version for migrations.
- All entity ids (campaign, facts, plan items, posts) are UUIDs created in the browser, so the document can be imported into an account unchanged.
- Saving: after sign-in the client sends `POST /api/campaigns` with the document and its `client_id`. The server inserts it idempotently on `(user_id, client_id)`, then the client clears the guest copy.
- Signed-in mode: the server is the source of truth. The client autosaves with debounce using `PUT /api/campaigns/{id}` and an integer `version` for optimistic concurrency.

## Consequences
- The server holds no guest data, which keeps the privacy claim simple and true. Prompts still go to the model provider; the UI and README say so.
- Clearing browser storage loses guest work. The UI shows a persistent "saved on this device" notice and offers Save at every step.
- Validation rules must be callable without a stored campaign. `domain/` functions take plain data, and endpoints such as `/api/posts/validate` and `/api/impact/analyze` exist for that reason.
- Business logic lives on the server, not duplicated in the client, to avoid drift.

## Alternatives considered
- Anonymous server sessions with a database row: simpler client, but stores unknown people's data and adds expiry jobs.
- Require login first: contradicts the BRD and loses the trial benefit.
