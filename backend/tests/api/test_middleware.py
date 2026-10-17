import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from helpers import facts_json

from app.core.config import Settings
from app.llm.base import LLMUnavailable
from app.main import create_app

SAMPLE = {"source": {"kind": "sample"}}


def test_mutating_call_without_header_is_forbidden(app):
    bare = TestClient(app)

    response = bare.post("/api/brief/extract", json=SAMPLE)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_wrong_header_value_is_forbidden(app):
    response = TestClient(app).post(
        "/api/brief/extract", json=SAMPLE, headers={"X-Requested-With": "XMLHttpRequest"}
    )

    assert response.status_code == 403


def test_get_requests_do_not_need_header(app):
    bare = TestClient(app, follow_redirects=False)

    assert bare.get("/api/health").status_code == 200
    assert bare.get("/api/auth/login/google").status_code != 403
    assert bare.get("/api/auth/callback/google").status_code != 403


def test_signed_in_users_get_the_user_limit(client, app, sample_text):
    client.get("/api/config")
    login = client.post("/api/auth/test-login", json={"email": "limit@example.org"})
    assert login.status_code < 300
    payload = {"source": {"kind": "text", "text": sample_text}}

    codes = [
        client.post("/api/brief/extract", json=payload).status_code
        for _ in range(app.state.settings.rate_guest_per_hour + 1)
    ]

    assert codes.count(429) == 0


def test_body_over_256_kb_is_rejected(client):
    response = client.post(
        "/api/brief/extract",
        content=b'{"source": {"kind": "text", "text": "' + b"a" * 300_000 + b'"}}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_streamed_body_over_limit_is_rejected(client):
    def chunks():
        for _ in range(10):
            yield b"a" * 40_000

    response = client.post(
        "/api/posts/validate", content=chunks(), headers={"content-type": "application/json"}
    )

    assert response.status_code == 413


def test_security_headers_on_api_and_spa(client):
    for path in ("/api/health", "/"):
        headers = client.get(path).headers
        csp = headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "https://fonts.googleapis.com" in csp
        assert "https://fonts.gstatic.com" in csp
        assert "frame-ancestors 'none'" in csp
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert headers["x-frame-options"] == "DENY"


def test_hsts_only_in_production(client, tmp_path):
    assert "strict-transport-security" not in client.get("/api/health").headers

    prod = Settings(
        _env_file=None, app_env="production", session_secret="a" * 64, static_dir=str(tmp_path)
    )
    headers = TestClient(create_app(prod)).get("/api/health").headers
    assert headers["strict-transport-security"].startswith("max-age=")


def test_cid_cookie_is_set_once(client):
    first = client.get("/api/config")
    assert "cid=" in first.headers["set-cookie"]
    assert "HttpOnly" in first.headers["set-cookie"]

    second = client.get("/api/config")
    assert "set-cookie" not in second.headers


def test_general_request_limit_returns_429(tmp_path):
    settings = Settings(
        _env_file=None, app_env="test", rate_ip_per_minute=3, static_dir=str(tmp_path)
    )
    limited = TestClient(create_app(settings))

    codes = [limited.get("/api/config").status_code for _ in range(4)]

    assert codes == [200, 200, 200, 429]
    response = limited.get("/api/config")
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["retry-after"]) >= 1
    assert limited.get("/api/health").status_code == 200


def euri_app(tmp_path, **extra):
    settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="euri",
        euri_api_key="sk-test",
        euri_model="gemma-4",
        static_dir=str(tmp_path),
        **extra,
    )
    return create_app(settings)


@respx.mock
def test_unavailable_euri_falls_back_to_labelled_mock(tmp_path, sample_text):
    respx.post(url__regex=r".*/chat/completions").mock(return_value=httpx.Response(401))
    app = euri_app(tmp_path, llm_fallback_to_mock=True)
    client = TestClient(app, headers={"X-Requested-With": "campaory"})

    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "text", "text": sample_text}}
    )

    assert response.status_code == 200
    assert response.headers["x-llm-provider"] == "mock"
    assert response.json()["meta"]["provider"] == "mock"
    assert response.json()["meta"]["is_mock"] is True


@respx.mock
def test_unavailable_euri_without_fallback_is_502(tmp_path, sample_text):
    respx.post(url__regex=r".*/chat/completions").mock(return_value=httpx.Response(401))
    client = TestClient(euri_app(tmp_path), headers={"X-Requested-With": "campaory"})

    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "text", "text": sample_text}}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_unavailable"


@pytest.mark.parametrize("fallback, status", [(True, 200), (False, 503)])
def test_daily_cap(tmp_path, sample_facts, fallback, status):
    app = euri_app(tmp_path, llm_daily_cap=0, llm_fallback_to_mock=fallback)

    class NeverCalled:
        name = "euri"
        model = "gemma-4"

        async def complete(self, **kwargs):
            raise LLMUnavailable("should not be called")

    app.state.gate.provider = NeverCalled()
    client = TestClient(app, headers={"X-Requested-With": "campaory"})

    response = client.post(
        "/api/posts/validate", json={"platform": "x", "text": "Hi", "facts": facts_json([])}
    )
    assert response.status_code == 200
    response = client.post(
        "/api/posts/generate",
        json={
            "facts": facts_json(sample_facts),
            "items": [
                {
                    "id": "8c7f3e8e-6b0a-4a51-9a39-1a2b3c4d5e6f",
                    "title": "Event announcement",
                    "stage": "pre",
                }
            ],
            "platforms": ["x"],
        },
    )

    assert response.status_code == status
    if fallback:
        assert response.headers["x-llm-provider"] == "mock"
    else:
        assert response.json()["error"]["code"] == "llm_unavailable"
