from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_config_reports_mock_provider_and_limits(client):
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "mock",
        "model": "Demo model",
        "llm_is_mock": True,
        "fallback_to_mock": False,
        "limits": {
            "guest_per_hour": 10,
            "guest_per_day": 30,
            "user_per_hour": 40,
            "max_items_per_generate": 4,
            "max_source_chars": 20000,
            "max_body_bytes": 262144,
        },
        "auth_providers": [],
    }


def test_config_for_euri_with_google_login(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="euri",
        euri_api_key="k",
        euri_model="google/gemma-4-26B-A4B-it",
        llm_fallback_to_mock=True,
        google_oauth_client_id="client-id",
        static_dir=str(tmp_path),
    )

    body = TestClient(create_app(settings)).get("/api/config").json()

    assert body["provider"] == "euri"
    assert body["model"] == "google/gemma-4-26B-A4B-it via Euri"
    assert body["llm_is_mock"] is False
    assert body["fallback_to_mock"] is True
    assert body["auth_providers"] == ["google"]
    assert "k" not in str(body.values()).replace("google", "")
