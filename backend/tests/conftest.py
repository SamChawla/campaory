from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.domain.facts import is_critical
from app.domain.schemas import Fact, Person
from app.main import create_app

SAMPLE_TEXT_PATH = Path(__file__).resolve().parents[2] / "samples" / "sample_event.txt"


def make_fact(key, value, status="confirmed", **kw) -> Fact:
    return Fact(id=uuid4(), key=key, value=value, status=status, critical=is_critical(key), **kw)


def build_sample_facts() -> list[Fact]:
    """The sample event, every fact confirmed."""
    return [
        make_fact("event_name", "Riverside Open Source Hack Day 2026"),
        make_fact("start_date", "2026-10-24"),
        make_fact("start_time", "10:00"),
        make_fact("end_time", "17:30"),
        make_fact("timezone", "Asia/Kolkata"),
        make_fact("venue", "Lakeview Co-working Hall"),
        make_fact("address", "14 Station Road, Indore"),
        make_fact("city", "Indore"),
        make_fact("event_mode", "offline"),
        make_fact("registration_url", "https://example.org/riverside-hackday/register"),
        make_fact("registration_deadline", "2026-10-22"),
        make_fact("registration_status", "Free entry"),
        make_fact("capacity", "80"),
        make_fact(
            "audience",
            "students and early-career developers who want to make their first open source "
            "contribution",
        ),
        make_fact(
            "mentors",
            [
                Person(name="Asha Verma", role="Python"),
                Person(name="Kabir Nair", role="JavaScript"),
            ],
        ),
        make_fact("judges", [Person(name="Meera Iyer")]),
        make_fact("partners", [Person(name="Lakeview Co-working", handle="@lakeviewhub")]),
        make_fact("hashtags", ["#RiversideHack", "#Hacktoberfest"]),
        make_fact("language", "en"),
    ]


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
