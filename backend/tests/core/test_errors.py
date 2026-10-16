import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import AppError, install_error_handlers


class Body(BaseModel):
    name: str


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/blocked")
    def blocked():
        raise AppError(
            422, "blocked", "Confirm the facts first.", details={"missing": ["audience"]}
        )

    @app.get("/limited")
    def limited():
        raise AppError(429, "rate_limited", "Try again in 12 minutes.", retry_after_seconds=720)

    @app.post("/echo")
    def echo(body: Body):
        return body

    @app.get("/crash")
    def crash():
        raise RuntimeError("secret campaign text")

    return TestClient(app, raise_server_exceptions=False)


def test_app_error_uses_error_shape(client):
    response = client.get("/blocked")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "blocked",
            "message": "Confirm the facts first.",
            "details": {"missing": ["audience"]},
        }
    }


def test_rate_limited_error_sets_retry_after_header(client):
    response = client.get("/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "720"
    assert response.json()["error"]["retry_after_seconds"] == 720


def test_request_validation_error_uses_error_shape(client):
    response = client.post("/echo", json={})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"][0]["loc"] == ["body", "name"]


def test_unhandled_error_hides_internals(client):
    response = client.get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "server_error"
    assert "secret" not in response.text
