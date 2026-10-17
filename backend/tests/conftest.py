import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        llm_provider="mock",
        static_dir=str(tmp_path / "static"),
        database_url="sqlite://",
    )


@pytest.fixture
def client(settings) -> TestClient:
    app = create_app(settings)
    Base.metadata.create_all(app.state.db_engine)
    return TestClient(app)
