"""Signed session cookie and the user dependencies (ADR-004).

The cookie holds only the user id; itsdangerous adds the issue time and the signature. CSRF is
covered by SameSite=Lax plus the global `X-Requested-With: campaory` check on mutating calls.
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import Settings
from app.core.errors import AppError
from app.db import repo
from app.db.session import DbSession

SESSION_COOKIE = "campaory_session"
SESSION_SALT = "campaory.session.v1"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600


@dataclass(frozen=True)
class SessionUser:
    id: UUID
    email: str
    name: str | None
    avatar_url: str | None

    def public(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
        }


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=SESSION_SALT)


def issue_session(response: Response, settings: Settings, user_id: UUID) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        _serializer(settings).dumps({"uid": str(user_id)}),
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )


def clear_session(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )


def session_user_id(request: Request) -> UUID | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = _serializer(request.app.state.settings).loads(
            token, max_age=SESSION_MAX_AGE_SECONDS
        )
    except BadSignature:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("uid"), str):
        return None
    try:
        return UUID(payload["uid"])
    except ValueError:
        return None


def optional_user(request: Request, db: DbSession) -> SessionUser | None:
    user_id = session_user_id(request)
    if user_id is None:
        return None
    user = repo.get_user(db, user_id)
    if user is None:
        return None
    return SessionUser(id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url)


def current_user(
    user: Annotated[SessionUser | None, Depends(optional_user)],
) -> SessionUser:
    if user is None:
        raise AppError(401, "unauthorized", "Sign in to continue.")
    return user


OptionalUser = Annotated[SessionUser | None, Depends(optional_user)]
CurrentUser = Annotated[SessionUser, Depends(current_user)]
