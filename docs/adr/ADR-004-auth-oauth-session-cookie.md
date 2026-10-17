# ADR-004: Sign-in with Google OAuth and a server session cookie

Status: Accepted, confirm provider before building. Date: 2026-10-16. Source: BRD v1.1 FR 23, FR 27, section 12 (Identity).

## Context
Saving a campaign requires an account. We do not want to store passwords, send emails, or build password reset. Time is short, so auth is the main schedule risk.

## Decision
- Google OAuth 2.0 / OIDC, authorization code flow, through Authlib (Starlette integration). Scopes: `openid email profile`.
- GitHub is an optional second provider, added only if Google is done and tested. The `identities` table is keyed by `(provider, subject)` so a second provider needs no migration.
- Session: signed cookie `campaory_session` (itsdangerous, `SESSION_SECRET`), `HttpOnly`, `Secure` in production, `SameSite=Lax`, 30-day lifetime (changed from 14 days on 17 Oct 2026 so returning organisers stay signed in through a campaign). The cookie holds only `user_id` and an issued-at time. Authlib keeps OAuth `state` and the PKCE verifier in a separate 10-minute cookie `campaory_oauth` scoped to `/api/auth`.
- Mutating requests from a signed-in session must carry `X-Requested-With: campaory` (checked server-side). With `SameSite=Lax` and JSON-only bodies this blocks simple cross-site form posts.
- OAuth `state` and PKCE are on. The post-login redirect target is restricted to relative paths.
- The server stores: provider, subject, email, display name, avatar URL. Nothing else from Google.
- Account deletion removes the user, identities and all campaigns (cascade). See FR 27.

## Consequences
- No password storage and no email sending.
- Requires a Google Cloud OAuth client, with the redirect URI registered for every host (localhost, onrender.com, the .tech domain). This is manual work; see HANDOFF.
- Google's consent screen in "testing" mode limits users to listed test accounts. For public use, set it to "In production" (basic scopes need no verification, but the unverified-app warning may appear). Plan for judges to see this screen.
- Sessions are cookie-only, so there is no server session store. Logging out clears the cookie; there is no server-side revocation before expiry. Acceptable for this scope.

## Alternatives considered
- Email magic links: needs an email provider and deliverability work.
- Passkeys or password auth: more build and more security surface.
- Managed auth (Clerk, Auth0, Supabase): faster, but adds a vendor and weakens the "open" story. Reasonable if Authlib setup blows the time box; decide by the end of day 1.
- No auth, capability links: rejected by the product owner. Saving requires login.
