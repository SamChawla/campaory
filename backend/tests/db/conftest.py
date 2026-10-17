import pytest
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.session import make_engine, make_session_factory


@pytest.fixture
def engine():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Session:
    with make_session_factory(engine)() as session:
        yield session
