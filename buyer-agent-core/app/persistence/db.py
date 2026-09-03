from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str):
    # pool_pre_ping: a dropped/idle Postgres connection is reconnected
    # transparently instead of surfacing as a confusing error on the next
    # request - the one bit of resilience worth having by default here.
    return create_engine(database_url, pool_pre_ping=True, future=True)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """One transaction per unit of work - commits on success, rolls back and
    re-raises on any exception, always closes."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
