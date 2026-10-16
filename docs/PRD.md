# Campaory: Product Requirements Document (PRD)

Version 1.1, 16 Oct 2026. Owner: Sumit S Chawla. Companion to the BRD (business needs). The PRD says what the product does and how we know it works. Requirement ids (FR, BR) are from the BRD.

## 1. Summary

Campaory turns one verified event brief into a coordinated campaign for LinkedIn, Instagram, WhatsApp and X. Anyone can try it as a guest. Signing in is needed only to save.

Positioning line: "Facts first. Then posts."

## 2. Goals and non-goals

Goals
1. A first-time visitor reaches a first approved, copyable post in 5 minutes or less, without an account.
2. No generated post contains an unconfirmed critical fact.
3. When a fact changes, the user sees exactly which unpublished posts to update.
4. A live deployed app plus a credible user story for the DEV submission by 19 Oct 12:29 PM IST.

Non-goals (MVP)
- Direct publishing, analytics, ads, teams, passwords, payments, poster OCR, Hindi/Hinglish quality guarantees.

## 3. Users and jobs

| User | Job to be done | Pain today |
|---|---|---|
| Community organizer (primary) | Announce an event and keep followers updated for weeks | Rewrites the same details for each platform, facts drift |
| Volunteer coordinator | Post from approved info | Not sure which version is current |
| Judge / first-time visitor | Understand the product in two minutes | Sign-up walls |

## 4. Key user stories and acceptance

Priorities follow BRD section 19. IDs link to BRD functional requirements.

| # | Story | FR | Acceptance (summary) |
|---|---|---|---|
| S1 | As a visitor I can try the product with no account | 21 | Landing to copied post with zero sign-in prompts |
| S2 | As a visitor I can paste a URL or text, or use a sample event | 01, 02 | Brief appears with source snippets per fact; sample works offline of any URL |
| S3 | I review and edit extracted facts before anything is written | 03, 04 | "Generate plan" disabled until BR01 facts are confirmed |
| S4 | I get a campaign calendar I can edit | 05, 06 | Dates are never after the event unless stage is post; drag/reorder and rename work |
| S5 | I get distinct posts per platform | 07, 11 | Four variants per item; limit validation visible; over-limit blocks approval |
| S6 | I can edit, revise and approve a post | 09, 10 | "Make shorter" changes only that post, previous text kept |
| S7 | I can copy a post and open the platform | 12 | Clipboard has exact text; opening never marks published (BR05) |
| S8 | I can set a reminder and see Upcoming | 13, 14 | Needs approved post and future time (BR06) |
| S9 | When I change a fact I see affected posts and proposed edits | 16, 17, 18 | Published posts unchanged (BR03); diff shows old and new |
| S10 | My guest work survives a reload | 22 | Reload restores brief, facts, plan, posts |
| S11 | I can save my campaign by signing in | 23, 24 | After login, the same campaign appears in my account unchanged |
| S12 | I can list, reopen and delete saved campaigns | 25, BR12 | Another account cannot open mine (404) |
| S13 | When I hit a limit I know why and when to retry | 26 | 429 shows retry time; on-screen campaign intact |
| S14 | I can delete my account | 27 (P1) | All rows removed |

## 5. Functional specification by screen

Screens are mocked in `docs/mockups/`. Sign-in and save are specified in UI_SPEC section 7.

1. Start: input (URL / text / sample), platform choice, language, tone. "Try a sample event" is a first-class button. Guest notice: "Saved on this device only. Sign in to keep it."
2. Facts: table of fields with status chip (Confirmed, Needs review, Missing, Superseded), source snippet, inline edit, confirm all. Blocking banner lists what is missing for BR01.
3. Plan: stages (Before, Event day, After), items with date, platform dots, reorder and edit. Dates computed in code.
4. Posts: per item, four platform cards with text, counter, validation, status. Actions: edit, make shorter/longer/warmer, regenerate, approve, copy, open, schedule, mark published.
5. Changes: edit a fact, see impacted posts, proposals with diff, accept or keep.
6. Upcoming and dashboard: counts per status, next scheduled posts, needs-review list.
7. Saved campaigns (signed in): list, open, delete.
8. Sign-in sheet and save banner: specified in UI_SPEC.

## 6. Rules summary (from BRD section 13)

BR01 generation gate. BR02 approval gate on facts. BR03 published immutable. BR04 fact change flags dependents. BR05 open is not publish. BR06 reminder needs approved and future. BR07 variants independent. BR08 user responsible. BR09 guest everything, saving needs login. BR10 guest data on device. BR11 import once then clear. BR12 owner-only access.

Added by design, not in the BRD: placeholders `[ADD: ...]` block approval (implemented under BR02); guard flags block approval until fixed. The BRD should be updated to say so in v1.2.

## 7. Non-functional requirements (targets)

| Area | Target |
|---|---|
| Time to first post (guest) | 5 minutes or less median |
| Extract latency | under 15 s p95 with progress shown |
| Posts generation | under 30 s for 8 items x 4 platforms, streamed in batches |
| Saved campaign load | under 2 s |
| Mobile | 360 px, no horizontal scroll |
| Accessibility | labels, keyboard operable, status not by colour only, reduced-motion respected |
| Privacy | Guest data not stored server-side; saved data deletable |
| Security | See HLD section 8 |

## 8. Success metrics

Same as BRD section 3. For the submission, report honestly: number of organizers who tried it, time to first post, corrections needed, how many guests chose to sign in and save, and one product change made from feedback.

## 9. Release criteria

BRD section 22, plus: the deployed URL works from a phone on mobile data; one demo video under 3 minutes; README with setup, model details, limitations, sample data.

## 10. Open questions

1. Which Gemma model id is actually available and good enough at JSON? Decide by the end of day 1.
2. Is Google OAuth consent screen set to production for judges? Check on day 2.
3. Which real organizers will test? Need three names by tomorrow morning; this is the weakest part of the plan so far.
4. Pricing statements in the BRD are indicative. Do not present them as validated.
