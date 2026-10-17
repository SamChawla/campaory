"""Engine and session wiring. Tables are created by Alembic; tests call create_all themselves."""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def make_engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _sqlite_foreign_keys)
    return engine


def _sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def install_database(app: FastAPI, url: str) -> None:
    engine = make_engine(url)
    app.state.db_engine = engine
    app.state.db_sessions = make_session_factory(engine)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.db_sessions() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
