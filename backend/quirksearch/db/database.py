"""SQLite connection management and transactions.

* ``PRAGMA foreign_keys = ON``   – SQLite enforces FKs only when asked, per connection.
* ``PRAGMA journal_mode = WAL``  – write-ahead log: readers never block the writer, so the
                                   API can serve searches while a crawl is indexing pages.
* ``PRAGMA synchronous = NORMAL``– durable at every checkpoint, much faster than FULL in WAL.
* ``busy_timeout``               – wait for a lock instead of failing immediately.

Connections are opened in autocommit mode (``isolation_level=None``) so transactions are
explicit: ``with transaction(conn): ...`` issues ``BEGIN IMMEDIATE`` … ``COMMIT``, or
``ROLLBACK`` if the block raises – the atomicity half of ACID.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 1


def connect(db_path: Path | str) -> sqlite3.Connection:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection, immediate: bool = True) -> Iterator[sqlite3.Connection]:
    """All-or-nothing unit of work."""
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables/indexes/triggers idempotently and record the schema version."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
