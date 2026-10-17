# Campaory: UI specification

Version 1.1. Visual source of truth: the approved mockups ([mockups/README](mockups/README.md)) and [tokens.css](mockups/tokens.css). Sections 1 to 6 describe what is mocked. Section 7 specifies screens that are not mocked.

## 1. Design intent

Not an "AI tool" look: no purple or blue gradients, no sparkle icons, no chat box as the main surface. The product is a workspace for facts and posts. Confident wide heavy type, a floating pill navigation, pill buttons, hand-drawn style underline on one key word, coloured platform circles, a forest, lime and coral palette, and purposeful motion.

Avoid: "AI" badges, magic-wand icons, generic gradient cards, stock illustrations.

## 2. Foundations

| Token | Value | Use |
|---|---|---|
| Ink | `#0B1F18` | text, primary buttons |
| Ground | `#F2F5F1` | page background |
| Surface | `#FFFFFF` | cards |
| Lime | `#C6F23B` | primary highlight, "needs attention" |
| Coral | `#FF6A4D` | accent, LinkedIn dot |
| Mint / Mint ink | `#D9F5E3` / `#0B3A27` | approved |
| Forest | `#0F3D2E` | Instagram dot (white text) |
| WhatsApp / X dots | `#7AE0B0` / `#8ED6FF` | platform circles |
| Muted | `#4F5E57`, `#5B6A63` | secondary text (check contrast on tints) |

Type: Archivo variable. Display and headings weight 800, width 118. UI weight 600 to 700. Body 15 px. Sizes: 60 / 44 / 34 (display by breakpoint), 34 h2, 22 h3, 20 lead, 15 body, 14 UI, 13 small.

Shape: pills (999 px) for buttons, chips and nav; 24 px cards; 16 px inner blocks; 10 px small controls.

Spacing: 4 px base; section gaps 64 to 96 px desktop, 40 px mobile; card padding 24 px desktop, 16 px mobile.

Breakpoints: 360 (min), 768, 1024, 1280. Content max width 1200.

## 3. Components

| Component | Spec |
|---|---|
| Nav | Floating pill, ink on ground, logo left, links centre, CTA right; collapses to a menu button under 768 |
| Button primary | Ink background, white text, pill, 44 px min height, hover lifts 2 px |
| Button secondary | White background, ink border 2 px |
| Button highlight | Lime background, ink text (single main action per screen) |
| Chip (status) | Pill with text label plus icon; colour is secondary. Confirmed = mint; Needs review = lime tint; Missing = peach; Superseded = grey with strikethrough label |
| Platform dot | 28 px circle with platform initial; colours from tokens |
| Fact row | Label, value (editable inline), status chip, source snippet disclosure, confirm check |
| Plan item | Date pill, title, purpose, platform dots, drag handle, overflow menu |
| Post card | Platform dot and name, status chip, text area, counter ("212 / 280"), validation messages, actions row |
| Diff | Word-level; removed in peach with strikethrough, added in lime tint; always has a text legend |
| Toast | Bottom centre, 3 s, `aria-live=polite` |
| Banner | Full width inside content column, lime wash; used for guest notice and blockers |

## 4. Screens (mocked)

1. Start: hero with the promise, input card (URL, text, sample), platform toggles, language, tone, primary action "Check the facts". "Try a sample event" visible without scrolling.
2. Confirm facts: grouped table, progress bar "5 of 5 needed facts confirmed", primary action disabled until BR01 satisfied, with a text explanation of what is missing.
3. Plan: three stage columns on desktop, vertical list on mobile; each item shows date and platforms; "Add item".
4. Posts: items as sections, four cards each; counters; "Make shorter / Warmer / More formal"; Approve; Copy; Open platform; Schedule; Mark published.
5. A fact changed: the edited fact at top, list of affected posts with reason, diff with proposed text, buttons "Update this post" and "Keep current"; a separate "Already public" list with a note.
6. Phone: single post review, sticky action bar (Approve, Copy, Open).

## 5. Motion

- Entrance: nav drops in, hero blocks rise with staggered delays (100 ms steps), platform circles pop and gently bob, underline draws.
- Scroll reveal: `animation-timeline: view()` where supported, otherwise no animation.
- Hover: cards lift 4 px with a soft shadow; buttons lift 2 px.
- Everything is inside `@media (prefers-reduced-motion: no-preference)`. With reduced motion the UI is static and complete.
- Do not animate layout properties; use `translate`, `scale` and `opacity`.

## 6. Responsive and accessibility rules

- 360 px: single column, no horizontal scroll, sticky bottom action bar on post review, touch targets 44 px.
- Every input has a visible label; errors are announced (`role=alert`) and tied with `aria-describedby`.
- Status is conveyed by text and icon, never colour alone.
- Contrast: body text at least 4.5:1. Verify muted greys on lime and mint tints; darken the tint use if it fails.
- Focus ring: 3 px ink, offset 3 px.
- Dialogs: focus trap, Escape closes, focus returns to the trigger.

## 7. Screens not yet mocked (build from this spec)

### 7.1 Guest notice
Inside the workspace, below the nav: lime-wash banner, text "Your work is saved on this device only. Sign in to keep it.", button "Save my campaign". Dismissible per session; returns on next visit. When the server has no sign-in method (`auth_providers` empty, as in the demo), the text is "Your work is saved in this browser. Clearing browser data removes it." and the button "Save now" writes to localStorage and toasts "Saved in this browser"; no sign-in sheet opens and the limit message drops "or sign in for a higher limit". A smaller version sits in the mobile header as a "Save" pill.

### 7.2 Sign-in sheet
Modal on desktop, bottom sheet on mobile. Title "Save your campaign". Body: "Sign in to keep this campaign and come back to it. Your current work comes with you." Primary button "Continue with Google" (standard Google mark, not recoloured). Secondary text button "Not now". Footer line: "We store your name, email and your campaigns. No passwords." Link to privacy note. If GitHub is enabled, a second equal button.
States: idle; redirecting (button disabled, "Opening Google..."); failed (`?auth=failed` shows a banner "Sign-in did not finish. Your work is still here.").

### 7.3 Post sign-in save
After redirect, show a toast "Saved. Your campaign is in your account." and replace the guest banner with a small "Saved" chip and last saved time. Autosave status text in the header: "Saving...", "Saved 12:41", or "Could not save. Retry".
Failure to import: banner "We could not save yet. Your work is still on this device." with a Retry button.

### 7.4 Saved campaigns
Route `/saved`. Cards: campaign name, event date, counts (approved, needs review, published), last edited, Open, Delete (confirm dialog naming the campaign; deleting cannot be undone). Empty state: "Nothing saved yet" with a "Start a campaign" button. Account menu in the nav: avatar, email, "Saved campaigns", "Sign out", "Delete account" (P1, confirm by typing DELETE).

### 7.5 Limit reached
Inline banner on the action area, never a full-page error: "You have used your free AI requests for now. Try again in 12 minutes, or sign in for a higher limit." Retry button disabled with a countdown. The campaign on screen stays editable.

### 7.6 Model badge
When `llm_is_mock` is true, a small badge near the generate button: "Demo model". Never hide it.

### 7.7 Errors and empty states
- Fetch failed: "We could not read that page. Paste the event text instead." with the text box focused.
- Generation partly failed: list failed items with "Retry these".
- Version conflict (saved mode): dialog "This campaign changed in another tab." Options "Load latest" and "Keep mine and overwrite".
- Offline: toast "You are offline. Changes are kept on this device."
- Storage unavailable: banner "This browser blocks storage. Your work will be lost if you close the page."

### 7.8 Copy and open
Copy shows a toast "Copied for LinkedIn". Open uses a new tab with `rel=noopener`. If the popup is blocked, show a link in the toast. Copy of Instagram adds the note "Paste into the Instagram app".

## 8. Content style

Plain words: "Check the facts", "Make the plan", "Write the posts", "Make shorter", "Update this post". Sentence case. No exclamation marks in system messages. Do not use "AI-powered", "magic", "supercharge".
