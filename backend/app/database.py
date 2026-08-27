"""
Database setup.

Uses SQLAlchemy's engine/session pattern. Defaults to SQLite (zero-config,
file-based) so the project runs immediately after `pip install`, but the
same models work unmodified against PostgreSQL once `DATABASE_URL` is
pointed at a real Postgres instance (per spec section 27, Postgres is the
target production database).

NOTE on migrations: the spec calls for proper migrations rather than
`create_all()` in production. This milestone uses `create_all()` for local
development speed (single command, no migration tooling to install yet).
Introducing Alembic is flagged as a near-term follow-up once the schema
has its first real consumer (see README "Known gaps").
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
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
    """Create all tables. Call once at startup for local/dev use."""
    from app import models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)
