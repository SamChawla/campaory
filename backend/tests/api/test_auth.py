from urllib.parse import parse_qs, urlparse

import pytest
import respx
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from support import XRW

from app.core.config import Settings
from app.core.security import SESSION_COOKIE
from app.db.models import Base, Identity, User
from app.main import create_app

METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
METADATA = {
    "issuer": "https://accounts.google.com",
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
    "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
}


def _client(tmp_path, **overrides) -> TestClient:
    values = dict(
        app_env="test",
        llm_provider="mock",
        static_dir=str(tmp_path / "static"),
        database_url="sqlite://",
        base_url="https://campaory.example",
        google_oauth_client_id="cid.apps.googleusercontent.com",
        google_oauth_client_secret="csecret",
    )
    values.update(overrides)
    app = create_app(Settings(**values))
    Base.metadata.create_all(app.state.db_engine)
    return TestClient(app, base_url="https://campaory.example", follow_redirects=False)


@pytest.fixture
def google(tmp_path) -> TestClient:
    return _client(tmp_path)


def _rows(client, model):
    with client.app.state.db_sessions() as db:
        return db.scalars(select(model)).all()


def _fake_token(monkeypatch, userinfo=None, error: Exception | None = None):
    async def authorize_access_token(self, request, **kwargs):
        if error is not None:
            raise error
        return {"access_token": "at", "userinfo": userinfo}

    monkeypatch.setattr(StarletteOAuth2App, "authorize_access_token", authorize_access_token)


GOOD_INFO = {
    "sub": "google-sub-1",
    "email": "Asha@Example.org",
    "email_verified": True,
    "name": "Asha Verma",
    "picture": "https://lh3.example/a.png",
}


# login


def test_login_redirects_to_google_with_pkce_and_fixed_redirect_uri(google):
    with respx.mock:
        respx.get(METADATA_URL).mock(return_value=Response(200, json=METADATA))
        response = google.get("/api/auth/login/google")

    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    query = parse_qs(location.query)
    assert (
        f"{location.scheme}://{location.netloc}{location.path}"
        == METADATA["authorization_endpoint"]
    )
    assert query["client_id"] == ["cid.apps.googleusercontent.com"]
    assert query["redirect_uri"] == ["https://campaory.example/api/auth/callback/google"]
    assert query["scope"] == ["openid email profile"]
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0]
    assert SESSION_COOKIE not in response.cookies


def test_login_is_404_without_google_client(tmp_path):
    client = _client(tmp_path, google_oauth_client_id="")

    response = client.get("/api/auth/login/google")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert client.get("/api/auth/callback/google").status_code == 404


# callback


def test_callback_creates_user_sets_cookie_and_redirects(google, monkeypatch):
    _fake_token(monkeypatch, GOOD_INFO)

    response = google.get("/api/auth/callback/google?code=c&state=s")

    assert response.status_code == 302
    assert response.headers["location"] == "/?auth=ok"
    assert SESSION_COOKIE in response.cookies
    users = _rows(google, User)
    assert [(u.email, u.name, u.avatar_url) for u in users] == [
        ("Asha@Example.org", "Asha Verma", "https://lh3.example/a.png")
    ]
    identity = _rows(google, Identity)[0]
    assert (identity.provider, identity.subject) == ("google", "google-sub-1")
    me = google.get("/api/me").json()
    assert me["user"]["email"] == "Asha@Example.org"


def test_callback_twice_reuses_the_user(google, monkeypatch):
    _fake_token(monkeypatch, GOOD_INFO)
    google.get("/api/auth/callback/google?code=c&state=s")
    _fake_token(monkeypatch, {**GOOD_INFO, "name": "Asha V"})

    google.get("/api/auth/callback/google?code=c&state=s")

    users = _rows(google, User)
    assert len(users) == 1
    assert users[0].name == "Asha V"


@pytest.mark.parametrize(
    "info",
    [
        {**GOOD_INFO, "email_verified": False},
        {k: v for k, v in GOOD_INFO.items() if k != "email"},
        {k: v for k, v in GOOD_INFO.items() if k != "sub"},
        None,
    ],
)
def test_callback_rejects_unusable_identity(google, monkeypatch, info):
    _fake_token(monkeypatch, info)

    response = google.get("/api/auth/callback/google?code=c&state=s")

    assert response.status_code == 302
    assert response.headers["location"] == "/?auth=failed"
    assert SESSION_COOKIE not in response.cookies
    assert _rows(google, User) == []


def test_callback_provider_error_redirects_failed(google, monkeypatch):
    _fake_token(monkeypatch, error=OAuthError(error="access_denied"))

    response = google.get("/api/auth/callback/google?error=access_denied")

    assert response.headers["location"] == "/?auth=failed"
    assert SESSION_COOKIE not in response.cookies


def test_callback_with_unknown_state_fails_without_network(google):
    with respx.mock:
        response = google.get("/api/auth/callback/google?code=c&state=forged")

    assert response.status_code == 302
    assert response.headers["location"] == "/?auth=failed"
    assert SESSION_COOKIE not in response.cookies


def test_callback_does_not_log_tokens(google, monkeypatch, caplog):
    _fake_token(monkeypatch, error=OAuthError(error="invalid_grant", description="code=secret"))

    google.get("/api/auth/callback/google?code=secret-code&state=s")

    assert "secret" not in caplog.text


# test-only login


def test_test_login_creates_session(client):
    response = client.post("/api/auth/test-login", json={"email": "b@example.org"}, headers=XRW)

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "b@example.org"
    assert client.get("/api/me").json()["user"]["email"] == "b@example.org"


def test_test_login_rejects_bad_email(client):
    response = client.post("/api/auth/test-login", json={"email": "nope"}, headers=XRW)

    assert response.status_code == 422


@pytest.mark.parametrize("env", ["development", "production"])
def test_test_login_does_not_exist_outside_test(tmp_path, env):
    client = _client(tmp_path, app_env=env, session_secret="z" * 64)

    response = client.post("/api/auth/test-login", json={"email": "b@example.org"}, headers=XRW)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# logout


def test_logout_clears_the_cookie(client):
    client.post("/api/auth/test-login", json={"email": "b@example.org"}, headers=XRW)

    response = client.post("/api/auth/logout", headers=XRW)

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert client.get("/api/me").json() == {"user": None}


def test_logout_without_session_is_fine(client):
    assert client.post("/api/auth/logout", headers=XRW).status_code == 204
