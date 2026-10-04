"""SQLAlchemy engine, session factory and declarative base.

Works with TiDB (``mysql+pymysql://...``, TLS required) and SQLite (local dev and tests).
"""

import ssl
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def make_engine(database_url: str) -> Engine:
    """Build an engine with the right options for SQLite or TiDB/MySQL."""
    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url or database_url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
    elif database_url.startswith("mysql"):
        # TiDB Cloud only accepts TLS connections; verify against the system CA store.
        kwargs["connect_args"] = {"ssl": ssl.create_default_context()}
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 300
    return create_engine(database_url, **kwargs)


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine built from DATABASE_URL."""
    return make_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    """Return the process-wide session factory."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def init_db(engine: Engine | None = None) -> None:
    """Create Developer 2's tables if they do not exist."""
    from app.core import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is closed after the request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
