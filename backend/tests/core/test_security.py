import time
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner, URLSafeTimedSerializer

from app.core import security
from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.core.security import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    CurrentUser,
    OptionalUser,
    clear_session,
    issue_session,
)
from app.db import repo
from app.db.models import Base
from app.db.session import install_database


def _app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings
    install_error_handlers(app)
    install_database(app, "sqlite://")
    Base.metadata.create_all(app.state.db_engine)

    @app.post("/login/{user_id}")
    def login(user_id: UUID, response: Response) -> dict:
        issue_session(response, settings, user_id)
        return {}

    @app.post("/logout")
    def logout(response: Response) -> dict:
        clear_session(response, settings)
        return {}

    @app.get("/optional")
    def maybe(user: OptionalUser) -> dict:
        return {"email": user.email if user else None}

    @app.get("/required")
    def required(user: CurrentUser) -> dict:
        return {"email": user.email, "id": str(user.id)}

    return app


def _make_user(app: FastAPI, email="asha@example.org"):
    with app.state.db_sessions() as db:
        return repo.upsert_user_from_identity(db, "google", email, email, "Asha", None)


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", session_secret="s" * 64)


@pytest.fixture
def app(settings):
    return _app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


def test_cookie_attributes(client, app):
    user = _make_user(app)

    response = client.post(f"/login/{user.id}")

    header = response.headers["set-cookie"].lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in header
    assert "samesite=lax" in header
    assert f"max-age={SESSION_MAX_AGE_SECONDS}" in header
    assert "path=/" in header
    assert "secure" not in header
    assert SESSION_MAX_AGE_SECONDS == 30 * 24 * 3600


def test_cookie_is_secure_in_production():
    prod = Settings(app_env="production", session_secret="p" * 64)
    app = _app(prod)
    user = _make_user(app)

    response = TestClient(app).post(f"/login/{user.id}")

    assert "secure" in response.headers["set-cookie"].lower()


def test_valid_cookie_identifies_user(client, app):
    user = _make_user(app)
    client.post(f"/login/{user.id}")

    assert client.get("/required").json() == {"email": "asha@example.org", "id": str(user.id)}
    assert client.get("/optional").json() == {"email": "asha@example.org"}


def test_cookie_holds_no_email_or_name(client, app):
    user = _make_user(app)
    client.post(f"/login/{user.id}")

    value = client.cookies[SESSION_COOKIE]
    assert "asha" not in value.lower()


def test_no_cookie(client):
    response = client.get("/required")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert client.get("/optional").json() == {"email": None}


def test_tampered_cookie_is_rejected(client, app):
    user = _make_user(app)
    client.post(f"/login/{user.id}")
    value = client.cookies[SESSION_COOKIE]
    flipped = value[:-1] + ("A" if value[-1] != "A" else "B")
    client.cookies.set(SESSION_COOKIE, flipped)

    assert client.get("/required").status_code == 401
    assert client.get("/optional").json() == {"email": None}


def test_cookie_signed_with_another_secret_is_rejected(client, app):
    user = _make_user(app)
    forged = URLSafeTimedSerializer("x" * 64, salt=security.SESSION_SALT).dumps(
        {"uid": str(user.id)}
    )
    client.cookies.set(SESSION_COOKIE, forged)

    assert client.get("/required").status_code == 401


def test_expired_cookie_is_rejected(client, app, settings, monkeypatch):
    user = _make_user(app)
    old = int(time.time()) - SESSION_MAX_AGE_SECONDS - 60
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: old)
    stale = security._serializer(settings).dumps({"uid": str(user.id)})
    monkeypatch.undo()
    client.cookies.set(SESSION_COOKIE, stale)

    assert client.get("/required").status_code == 401


@pytest.mark.parametrize("payload", [{"uid": "not-a-uuid"}, {"nope": 1}, "string", None])
def test_signed_but_malformed_payload_is_rejected(client, settings, payload):
    client.cookies.set(SESSION_COOKIE, security._serializer(settings).dumps(payload))

    assert client.get("/required").status_code == 401


def test_cookie_for_unknown_user_is_rejected(client, settings):
    client.cookies.set(SESSION_COOKIE, security._serializer(settings).dumps({"uid": str(uuid4())}))

    assert client.get("/required").status_code == 401
    assert client.get("/optional").json() == {"email": None}


def test_clear_session_expires_cookie(client, app):
    user = _make_user(app)
    client.post(f"/login/{user.id}")

    response = client.post("/logout")

    header = response.headers["set-cookie"].lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "max-age=0" in header
    assert client.get("/required").status_code == 401
