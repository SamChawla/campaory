# Campaory: Deployment (Render)

Verify every Render and Google step against current dashboards; screens and field names change. `render.yaml` in the repo root has not been tested against Render yet (written offline).

## 1. One-time setup

1. Push the repo to GitHub.
2. Render: New → Blueprint → select the repo. It reads `render.yaml` and creates the web service and a Postgres database.
3. Set secrets in the Render dashboard (they are `sync: false` in the blueprint): `SESSION_SECRET`, `EURI_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `SENTRY_DSN` (optional), `BASE_URL`.
4. First deploy: watch logs; migrations run on start (`alembic upgrade head`).
5. Open `<service>.onrender.com/api/health`.

## 2. Google OAuth client

1. Google Cloud console → APIs & Services → OAuth consent screen: app name Campaory, support email, scopes `openid email profile`, publishing status "In production" for public users (otherwise only test users can sign in).
2. Credentials → Create OAuth client ID → Web application.
3. Authorized redirect URIs (exact match, no trailing slash differences):
   - `http://localhost:8000/api/auth/callback/google`
   - `https://<service>.onrender.com/api/auth/callback/google`
   - `https://<your-name>.tech/api/auth/callback/google`
4. Copy client id and secret into Render and `.env`.
5. `BASE_URL` must match the host users use, because the redirect URI is built from it.

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
