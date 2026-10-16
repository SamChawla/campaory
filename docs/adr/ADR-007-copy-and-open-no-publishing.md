# ADR-007: Copy and open the platform; no direct publishing

Status: Accepted. Date: 2026-10-16. Source: BRD scope and non-goals.

## Context
Direct publishing needs OAuth apps and review for LinkedIn, Instagram and X, and WhatsApp Business has its own approval. None of this fits the time box, and automatic posting raises the cost of a wrong post.

## Decision
- Each platform card has Copy, and Open where a web share intent exists:
  - LinkedIn: `https://www.linkedin.com/sharing/share-offsite/?url=` for a link share, otherwise copy-then-open `https://www.linkedin.com/feed/`.
  - X: `https://twitter.com/intent/tweet?text=` (text pre-filled; URL-encoded).
  - WhatsApp: `https://wa.me/?text=`.
  - Instagram: no web composer. Copy text and show a short "paste into the app" note.
- "Mark as published" is a manual user action and the only way a post reaches `published`.
- Reminders are shown in the Plan view and can be exported as an `.ics` file (stretch). No push notifications or email in MVP.

## Consequences
- Zero third-party posting credentials to secure.
- The user stays in control, which also supports the trust story.
- Share-intent URLs can change; keep them in one module (`frontend/src/lib/share.ts`) and test the encoding.

## Alternatives considered
- Official posting APIs: out of time and review scope.
- Scheduling bots: same, and risks account bans.
