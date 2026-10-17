"""Google OAuth (authorization code + PKCE via Authlib) and logout. ADR-004.

Authlib keeps `state` and the PKCE verifier in a short-lived signed cookie scoped to /api/auth.
The app session itself is the separate `campaory_session` cookie from core/security.py.
"""

import logging
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import SessionUser, clear_session, issue_session
from app.db import repo
from app.db.session import DbSession

log = logging.getLogger("campaory.auth")

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
CALLBACK_PATH = "/api/auth/callback/google"
OAUTH_STATE_COOKIE = "campaory_oauth"
OAUTH_STATE_MAX_AGE_SECONDS = 600


def redirect_uri(settings: Settings) -> str:
    return settings.base_url.rstrip("/") + CALLBACK_PATH


def install(app: FastAPI, settings: Settings) -> None:
    """Register the Google client and the state cookie middleware when Google is configured."""
    app.state.oauth = None
    if not settings.google_oauth_client_id:
        return
    oauth = OAuth()
    oauth.register(
        "google",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        server_metadata_url=GOOGLE_METADATA_URL,
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )
    app.state.oauth = oauth
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=OAUTH_STATE_COOKIE,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        path="/api/auth",
        same_site="lax",
        https_only=settings.is_production,
    )


def router_for(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/auth")
    router.add_api_route("/login/google", login_google, methods=["GET"])
    router.add_api_route("/callback/google", callback_google, methods=["GET"])
    router.add_api_route("/logout", logout, methods=["POST"], status_code=204)
    if settings.app_env == "test":
        router.add_api_route("/test-login", fake_login, methods=["POST"])
    return router


def _google(request: Request):
    oauth = request.app.state.oauth
    if oauth is None:
        raise AppError(404, "not_found", "Google sign-in is not configured.")
    return oauth.google


async def login_google(request: Request) -> Response:
    google = _google(request)
    return await google.authorize_redirect(request, redirect_uri(request.app.state.settings))


def _failed() -> RedirectResponse:
    return RedirectResponse("/?auth=failed", status_code=302)


async def callback_google(request: Request, db: DbSession) -> Response:
    google = _google(request)
    try:
        token = await google.authorize_access_token(request)
    except Exception as exc:  # any provider, state or network failure ends the same way
        log.warning("google sign-in failed: %s", type(exc).__name__)
        return _failed()
    info = token.get("userinfo") or {}
    subject, email = info.get("sub"), info.get("email")
    if not subject or not email or info.get("email_verified") is not True:
        log.warning("google sign-in failed: unusable identity")
        return _failed()
    user = await run_in_threadpool(
        repo.upsert_user_from_identity,
        db,
        "google",
        str(subject),
        str(email),
        info.get("name"),
        info.get("picture"),
    )
    response = RedirectResponse("/?auth=ok", status_code=302)
    issue_session(response, request.app.state.settings, user.id)
    return response


def logout(request: Request, response: Response) -> None:
    clear_session(response, request.app.state.settings)


class FakeLoginRequest(BaseModel):
    email: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)]


def fake_login(body: FakeLoginRequest, request: Request, response: Response, db: DbSession):
    """Only mounted when APP_ENV=test: signs in as `email` without Google (LLD 9)."""
    user = repo.upsert_user_from_identity(
        db, "test", body.email.lower(), body.email, body.email.split("@")[0], None
    )
    issue_session(response, request.app.state.settings, user.id)
    profile = SessionUser(id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url)
    return {"user": profile.public()}
