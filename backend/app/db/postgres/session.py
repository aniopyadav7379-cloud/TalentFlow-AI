"""
Database engine/session management.

`get_engine`/`get_sessionmaker` accept an explicit URL so tests can point at
SQLite in-memory without touching global state, while `get_db` (the FastAPI
dependency) uses the configured settings for real requests.
"""
from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_engine(database_url: str | None = None):
    url = database_url or get_settings().DATABASE_URL
    is_sqlite = url.startswith("sqlite")
    is_sqlite_memory = is_sqlite and ":memory:" in url

    kwargs = {"echo": get_settings().DATABASE_ECHO, "pool_pre_ping": not is_sqlite_memory}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    if is_sqlite_memory:
        # Without StaticPool, every new connection to ':memory:' gets its own
        # empty database — sessions would each see a different DB.
        kwargs["poolclass"] = StaticPool

    return create_engine(url, **kwargs)


def get_sessionmaker(database_url: str | None = None) -> sessionmaker:
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


# Default (production/dev) session factory, lazily built on first use.
_default_sessionmaker: sessionmaker | None = None


def _get_default_sessionmaker() -> sessionmaker:
    global _default_sessionmaker
    if _default_sessionmaker is None:
        _default_sessionmaker = get_sessionmaker()
    return _default_sessionmaker


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped session, always closed."""
    db = _get_default_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    """Context manager for scripts/tests: commits on success, rolls back on error."""
    Session_ = get_sessionmaker(database_url)
    db = Session_()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
