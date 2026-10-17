# Campaory: Deployment (Render)

Verify every Render and Google step against current dashboards; screens and field names change. `render.yaml` in the repo root has not been tested against Render yet (written offline).

## 1. One-time setup

1. Push the repo to GitHub.
2. Render: New → Blueprint → select the repo. It reads `render.yaml` and creates the web service and a Postgres database.
3. Set secrets in the Render dashboard (they are `sync: false` in the blueprint): `SESSION_SECRET`, `GOOGLE_API_KEY`, `GEMMA_MODEL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `SENTRY_DSN` (optional), `BASE_URL`.
4. First deploy: watch logs; migrations run on start (`alembic upgrade head && uvicorn ...` in the Dockerfile `CMD`).
5. Open `<service>.onrender.com/api/health`.

## 2. Google OAuth client

1. Google Cloud console → APIs & Services → OAuth consent screen (Google Auth Platform → Branding / Audience / Data access in the newer console): app name Campaory, user support email, developer contact email, scopes `openid`, `email`, `profile` (no sensitive scopes, so no verification review). Audience "External". Publishing status: "Testing" limits sign-in to the listed test users (add your own Google accounts there for local checks); switch to "In production" before judges or trial organisers use it.
2. Credentials → Create credentials → OAuth client ID → Application type "Web application", name `Campaory`.
3. Authorized redirect URIs. Exact match: scheme, host, port and path, no trailing slash. The app builds the URI as `BASE_URL + /api/auth/callback/google`:
   - `http://localhost:8000/api/auth/callback/google` (local with `BASE_URL=http://localhost:8000`; after sign-in you land on `:8000/?auth=ok`, which serves the built SPA from `backend/static`)
   - optional: `http://localhost:5173/api/auth/callback/google` if you run `make dev` and want to land back in the Vite dev server; set `BASE_URL=http://localhost:5173` (the Vite proxy forwards `/api`)
   - `https://<service>.onrender.com/api/auth/callback/google` (the Render service URL, e.g. `https://campaory.onrender.com/api/auth/callback/google`)
   - `https://<your-name>.tech/api/auth/callback/google` (once the custom domain is attached)
4. Authorized JavaScript origins are not needed (the browser never talks to Google directly; the flow is server-side).
5. Copy the client id and secret into `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` in Render and in `backend/.env`. Without a client id, `/api/auth/login/google` returns 404 and the app stays guest-only.
6. `BASE_URL` must be the host users actually use (`http://localhost:8000` locally, `https://<service>.onrender.com` on Render, no trailing slash), because the redirect URI is built from it. A mismatch shows Google's `redirect_uri_mismatch` error.
7. Check: open `<BASE_URL>/api/auth/login/google`, sign in, and you should land on `/?auth=ok`; `GET /api/me` then returns your profile. `/?auth=failed` means the callback rejected the response (denied consent, expired state after 10 minutes, or an unverified email).

## 3. Google AI Studio (Gemma)

1. Create an API key at aistudio.google.com.
2. List available models with the models API (see HANDOFF 3) and pick the Gemma id you will use; set `GEMMA_MODEL`.
3. Free-tier quotas are small; ADR-008 limits exist for this reason. Check the quota page before the demo.

## 4. .tech domain

1. Claim the promo from hacktoberfest.com/my/promos (deadline per the challenge page; do this early, it can take time).
2. Render service → Settings → Custom Domains → add the domain; copy the DNS records Render shows into the registrar's DNS panel.
3. Wait for TLS issuance; update `BASE_URL` and the Google redirect URI; redeploy.
4. Verify login from the new host.

## 5. Release routine

```
git push origin main        # Render auto-deploys
curl -s https://<host>/api/health
# smoke: open the site, "Try a sample event", generate posts, confirm Demo model badge is absent when LLM_PROVIDER=gemma
```

Rollback: Render dashboard → Deploys → Rollback. Migrations are additive; avoid destructive migrations before submit.

## 6. Free tier notes

- The service sleeps after inactivity; the first request takes a while. Ping `/api/health` a few minutes before any demo or trial.
- The free Postgres has limits and may expire on some plans; export anything you need before submission and check the current Render policy.
- In-memory rate limits reset on every deploy and restart.

## 7. Configuration matrix

| Setting | Local | Production |
|---|---|---|
| `APP_ENV` | development | production |
| `LLM_PROVIDER` | mock | gemma |
| `LLM_FALLBACK_TO_MOCK` | false | true only during live demos with a visible badge |
| `DATABASE_URL` | sqlite | Render internal URL |
| Cookies | not Secure | Secure, HttpOnly, Lax |
