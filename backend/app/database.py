"""SQLite + SQLAlchemy setup.

The ORM is used throughout so that all queries are parameterized and the first
challenge can never accidentally become an SQL-injection challenge (plan 16).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# check_same_thread=False is required because FastAPI may use the connection
# from different threads; SQLite is otherwise single-threaded.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables and seed baseline rows. Safe to call repeatedly."""
    # Import models so they register with the metadata before create_all.
    from . import models  # noqa: F401  (side-effect import)

    Base.metadata.create_all(bind=engine)

    from .services.seed import seed_all

    with SessionLocal() as session:
        seed_all(session)
        session.commit()


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
