# Campaory: Design overview (v1.1)

Supersedes the earlier "no accounts" design. This is the short version; details are in the linked documents.

| Need | Document |
|---|---|
| What and why, requirements | `Campaory_Business_Requirements_Document_v1.1.docx`, [PRD](PRD.md) |
| Visual design, screens, motion | [UI_SPEC](UI_SPEC.md), [mockups](mockups/README.md) |
| Components, flows, diagrams | [ARCHITECTURE](ARCHITECTURE.md) |
| System-level design | [HLD](HLD.md) |
| API, schemas, algorithms | [LLD](LLD.md) |
| Why we chose what we chose | [ADRs](adr/README.md) |

## Scope cut versus the BRD

IN (MVP for the challenge):
- Guest mode for the whole flow (FR 21 to FR 24, BR 09 to BR 11)
- URL or pasted text, fact review, plan, four platform variants, edit, approve, "make shorter"
- Copy and open platform, upcoming list, change impact with redraft and diff, status dashboard
- Google sign-in, save, list, reopen, delete a campaign (FR 23 to FR 25)
- Rate limits (FR 26), 360 px mobile

OUT, listed as roadmap in the README:
- Poster OCR, Hindi and Hinglish, saved brand voice, real reminder delivery, CSV export, account deletion UI (P1), second sign-in provider (P1)

If time runs out, cut in this order: GitHub login, version-compare polish, `.ics` export, Ollama. Do not cut: guest flow, change-impact demo, fact guard, Google login + save.

## Core design decisions

1. Guest first. The server is stateless for guests; the browser keeps the campaign document ([ADR-003](adr/ADR-003-guest-first-stateless-api.md)).
2. Sign in only to save. After sign-in the guest document is imported once and the local copy is cleared ([ADR-004](adr/ADR-004-auth-oauth-session-cookie.md)).
3. Facts are owned by code. The model writes copy; the guard checks every URL, date, time, amount and handle ([ADR-005](adr/ADR-005-deterministic-fact-guard.md)).
4. Model behind an adapter, with mock for tests and demos ([ADR-002](adr/ADR-002-llm-provider-adapter.md)).
5. Published posts are never touched; affected drafts are proposals, not rewrites ([ADR-006](adr/ADR-006-change-impact-by-facts-used.md)).
6. No direct publishing ([ADR-007](adr/ADR-007-copy-and-open-no-publishing.md)).

## Honest risks

- Auth plus save adds roughly a third of the backend work. Build the guest flow first and keep it shippable at every step.
- The Gemma model id and its JSON behaviour on the hosted API are unverified. Verify on day 1 in 15 minutes ([HANDOFF](HANDOFF.md), section 3).
- Sign-in and save screens are not in the mockups. They are specified in UI_SPEC section 7 and must be built from that spec.
- The guard will produce false positives. Budget time to tune it against the PyData Indore sample.
