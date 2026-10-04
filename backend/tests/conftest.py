"""Shared fixtures: in-memory SQLite, a FastAPI test client and the Maya profile."""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["USE_STUBS"] = "true"
os.environ["USE_TIDB_RETRIEVAL"] = "false"
os.environ["ALLOW_UNREVIEWED_KNOWLEDGE"] = "false"
os.environ["ALLOW_CANDIDATE_REQUIREMENT_MAPPINGS"] = "false"
os.environ["ALLOW_DRAFT_REGISTRY"] = "false"

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.api.main import app  # noqa: E402
from app.api.routes_dev import load_maya_fixture  # noqa: E402
from app.contracts.facts import BusinessProfile  # noqa: E402
from app.core.db import get_session, init_db, make_engine  # noqa: E402
from app.core.settings import get_settings  # noqa: E402


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    """A fresh in-memory database per test."""
    engine = make_engine("sqlite://")
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def maya() -> BusinessProfile:
    return BusinessProfile(business_id="maya", profile_version=1, **load_maya_fixture().model_dump())


@pytest.fixture
def agent_mode(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Pin AGENT_MODE (and escalation) for one test, whatever the shipped default is."""

    def set_mode(mode: str, escalation: bool = True) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "agent_mode", mode)
        monkeypatch.setattr(settings, "escalation_enabled", escalation)

    return set_mode
