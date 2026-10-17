from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.models import Base
from app.db.session import make_engine

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["database_url"] = url
    return cfg, url


def test_upgrade_head_creates_every_table(alembic_cfg):
    cfg, url = alembic_cfg

    command.upgrade(cfg, "head")

    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert set(Base.metadata.tables) <= tables


def test_migration_matches_models(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def _check_names(engine) -> dict[str, set[str]]:
    inspector = inspect(engine)
    return {
        table: {ck["name"] for ck in inspector.get_check_constraints(table)}
        for table in Base.metadata.tables
    }


def test_migration_check_constraints_match_models(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    migrated = make_engine(url)
    fresh = make_engine("sqlite://")
    Base.metadata.create_all(fresh)

    assert _check_names(migrated) == _check_names(fresh)
    assert "ck_posts_status" in _check_names(migrated)["posts"]
    migrated.dispose()
    fresh.dispose()


def test_downgrade_to_base_drops_tables(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "base")

    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert not set(Base.metadata.tables) & tables


def test_migrated_email_index_ignores_case(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    engine = make_engine(url)
    insert = text(
        "INSERT INTO users (id, email, created_at) VALUES (:id, :email, '2026-10-17 00:00:00')"
    )

    with engine.begin() as conn:
        conn.execute(insert, {"id": "a" * 32, "email": "Asha@Example.org"})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert, {"id": "b" * 32, "email": "asha@example.org"})
    engine.dispose()
