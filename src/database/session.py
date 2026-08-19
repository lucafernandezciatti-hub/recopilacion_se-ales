"""Sesión y creación del esquema."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import database_url
from src.database.models import Base

_engine = None
_SessionFactory = None


def engine():
    global _engine
    if _engine is None:
        url = database_url()
        kwargs = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
    return _engine


def session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def init_db() -> None:
    Base.metadata.create_all(engine())


@contextmanager
def get_session() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
