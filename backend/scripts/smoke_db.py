"""Verify the configured TiDB connection, TLS, and current schema bootstrap.

Run from ``backend/``: ``python scripts/smoke_db.py``.
The script never prints the database URL, user name, or password.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.core.db import get_engine, init_db  # noqa: E402


def main() -> None:
    engine = get_engine()
    init_db(engine)

    with engine.connect() as connection:
        row = connection.execute(text("SELECT DATABASE() AS database_name, VERSION() AS version")).mappings().one()
        raw_connection = connection.connection.driver_connection
        if not getattr(raw_connection, "_secure", False):
            raise RuntimeError("TiDB connection did not negotiate TLS")
        cipher = raw_connection._sock.cipher()  # PyMySQL exposes the negotiated TLS socket here.

    tables = inspect(engine).get_table_names()
    print(f"Connected to database: {row['database_name']}")
    print(f"TiDB version: {row['version']}")
    print(f"TLS cipher: {cipher[0] if cipher else 'unknown'}")
    print(f"Current tables: {', '.join(sorted(tables)) or '(none)'}")


if __name__ == "__main__":
    main()
