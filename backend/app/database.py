"""
Database setup.

Uses SQLAlchemy's engine/session pattern. Defaults to SQLite (zero-config,
file-based) so the project runs immediately after `pip install`, but the
same models work unmodified against PostgreSQL once `DATABASE_URL` is
pointed at a real Postgres instance (per spec section 27, Postgres is the
target production database).

NOTE on migrations: schema changes go through Alembic (`backend/alembic/`,
`alembic upgrade head`) — see that directory's `env.py`, which reads its
DB URL from `settings.database_url` rather than a static `alembic.ini`
value, same as everything else in this app. `init_db()` below still uses
`create_all()`, but only for throwaway/in-memory test databases now; the
app's own startup no longer calls it, so Alembic-managed schema and
`create_all()` never fight over the same tables.
"""
from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

if settings.database_url.startswith("sqlite:///") and settings.database_url != "sqlite:///:memory:":
    # Make sure the SQLite file's parent directory exists (e.g. the
    # default ~/.trading_ambassador/) — SQLite won't create it for us.
    db_path = Path(settings.database_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables directly, bypassing Alembic - for a throwaway or
    in-memory test database only. The running app uses `alembic upgrade
    head` instead (see module docstring)."""
    from app import models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)
