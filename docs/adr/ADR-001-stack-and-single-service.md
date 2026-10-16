# ADR-001: FastAPI + React (Vite) + PostgreSQL as one Render service

Status: Accepted. Date: 2026-10-16.

## Context
Three days to a deployable product, one developer, a mobile-first UI with real interaction (inline editing, diffs). The developer is strongest in Python. The project must be live on a public URL and on a .tech domain.

## Decision
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx.
- Frontend: React 18, Vite, TypeScript, React Router, Zustand. Plain CSS with design tokens, no CSS framework.
- Database: PostgreSQL in production, SQLite for local tests.
- Deployment: one Docker web service on Render. FastAPI serves `/api/*` and the built SPA, with an SPA fallback route.

## Consequences
- One URL, one deploy, no CORS in production.
- Two toolchains (Python and Node). A Docker multi-stage build hides that in CI and on Render.
- Free-tier cold starts on Render. The first request after idle is slow; mention in the README and warm the app before demos.

## Alternatives considered
- Django + HTMX: fastest for the developer and no frontend build, but the interactive diff and inline edit screens, and the animated UI in the mockups, take more effort. Rejected on interaction quality, not on speed.
- Next.js full-stack: one language, but no benefit from Python domain code and more risk debugging TypeScript under time pressure.
- Separate frontend and backend services: more moving parts and CORS for no gain.
