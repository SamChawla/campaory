import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_use_mock_provider():
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert settings.app_env == "development"


def test_production_requires_session_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", session_secret="")


def test_production_rejects_example_session_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            session_secret="change-me-to-64-random-hex-chars",
        )


def test_unknown_provider_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="gpt")


def test_postgres_url_uses_psycopg_driver():
    settings = Settings(_env_file=None, database_url="postgresql://u:p@h/db")

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_euri_provider_defaults_to_euron_base_url():
    settings = Settings(_env_file=None, llm_provider="euri")

    assert settings.llm_provider == "euri"
    assert settings.euri_base_url == "https://api.euron.one/api/v1/euri"


@pytest.mark.parametrize("provider", ["gemma", "ollama"])
def test_cut_providers_are_rejected(provider):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider=provider)


def test_cut_provider_settings_are_gone():
    fields = Settings.model_fields

    for name in ("google_api_key", "gemma_model", "ollama_url", "ollama_model"):
        assert name not in fields
