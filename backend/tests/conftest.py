import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(app_env="test", llm_provider="mock", static_dir=str(tmp_path / "static"))


@pytest.fixture
def client(settings) -> TestClient:
    return TestClient(create_app(settings))
