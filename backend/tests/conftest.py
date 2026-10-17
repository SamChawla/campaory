import pytest
from fastapi.testclient import TestClient
from support import SAMPLE_TEXT_PATH, build_sample_facts

from app.core.config import Settings
from app.db.models import Base
from app.domain.schemas import Fact
from app.main import create_app


@pytest.fixture
def sample_text() -> str:
    return SAMPLE_TEXT_PATH.read_text(encoding="utf-8")


@pytest.fixture
def sample_facts() -> list[Fact]:
    return build_sample_facts()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        llm_provider="mock",
        static_dir=str(tmp_path / "static"),
        database_url="sqlite://",
    )


@pytest.fixture
def app(settings):
    app = create_app(settings)
    Base.metadata.create_all(app.state.db_engine)
    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app, headers={"X-Requested-With": "campaory"})
