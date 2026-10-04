"""SQLAlchemy engine, session factory and declarative base.

Works with TiDB (``mysql+pymysql://...``, TLS required) and SQLite (local dev and tests).
"""

import ssl
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

import certifi
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_TIDB_TLS_QUERY_KEYS = frozenset(
    {
        "ssl_ca",
        "ssl_capath",
        "ssl_cert",
        "ssl_key",
        "ssl_cipher",
        "ssl_check_hostname",
        "ssl_verify_cert",
        "ssl_verify_identity",
    }
)


def _as_bool(value: str | bool | None, name: str) -> bool:
    """Parse an optional URL boolean, rejecting ambiguous TLS settings."""
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if value.lower() in {"1", "true", "yes"}:
        return True
    if value.lower() in {"0", "false", "no"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _tidb_url_and_tls_context(database_url: str) -> tuple[URL, ssl.SSLContext]:
    """Build one verified TLS context from a TiDB Cloud SQLAlchemy URL.

    SQLAlchemy translates ``ssl_ca`` in a URL into a nested PyMySQL ``ssl`` dictionary.
    Passing another ``ssl`` object through ``connect_args`` can overwrite that dictionary.
    Consume the Console-provided TLS options here instead, then pass PyMySQL exactly one
    verified context.
    """
    url = make_url(database_url)
    query = dict(url.query)
    ca_file = query.get("ssl_ca")
    ca_path = query.get("ssl_capath")
    verify_cert = _as_bool(query.get("ssl_verify_cert"), "ssl_verify_cert")
    verify_identity = _as_bool(query.get("ssl_verify_identity"), "ssl_verify_identity")
    if not verify_cert or not verify_identity:
        raise ValueError("TiDB Cloud requires certificate and hostname verification")

    if ca_file and not ca_path and not Path(ca_file).exists():
        # The TiDB Console suggests an OS-specific bundle (e.g. macOS's /etc/ssl/cert.pem) that is
        # absent on other platforms, so one shared DATABASE_URL cannot name a path valid everywhere.
        # certifi trusts the same public CAs, so verification stays on.
        ca_file = certifi.where()

    cleaned_query = {key: value for key, value in query.items() if key not in _TIDB_TLS_QUERY_KEYS}
    return url.set(query=cleaned_query), ssl.create_default_context(cafile=ca_file, capath=ca_path)


def make_engine(database_url: str) -> Engine:
    """Build an engine with the right options for SQLite or TiDB/MySQL."""
    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url or database_url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
    elif database_url.startswith("mysql"):
        # TiDB Cloud only accepts TLS connections. Normalize the Console URL's TLS
        # parameters first so PyMySQL receives one verified SSL context.
        database_url, tls_context = _tidb_url_and_tls_context(database_url)
        kwargs["connect_args"] = {"ssl": tls_context}
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
