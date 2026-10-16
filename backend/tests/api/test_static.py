import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def spa_client(tmp_path) -> TestClient:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Campaory</title>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    settings = Settings(app_env="test", llm_provider="mock", static_dir=str(static))
    return TestClient(create_app(settings))


def test_root_serves_index(spa_client):
    response = spa_client.get("/")

    assert response.status_code == 200
    assert "Campaory" in response.text


def test_unknown_client_route_falls_back_to_index(spa_client):
    response = spa_client.get("/facts")

    assert response.status_code == 200
    assert "Campaory" in response.text


def test_assets_are_served(spa_client):
    response = spa_client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_missing_asset_is_404_not_index(spa_client):
    response = spa_client.get("/assets/missing.js")

    assert response.status_code == 404


def test_unknown_api_path_is_json_even_with_spa(spa_client):
    response = spa_client.get("/api/x")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_path_traversal_does_not_escape_static_dir(spa_client):
    response = spa_client.get("/..%2F..%2Fpyproject.toml")

    assert "build-system" not in response.text
