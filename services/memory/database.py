"""Database setup for the SQLite operational memory store."""

from collections.abc import Callable
from datetime import UTC
from typing import Any

from sqlalchemy import DateTime, Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    """Base for operational-memory tables."""


class UTCDateTime(TypeDecorator[object]):
    """Persist UTC timestamps and always return timezone-aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: object, dialect: Any) -> object:
        if value is None:
            return None
        from datetime import datetime

        if not isinstance(value, datetime):
            raise TypeError("UTCDateTime requires datetime values")
        timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: object, dialect: Any) -> object:
        if value is None:
            return None
        from datetime import datetime

        if not isinstance(value, datetime):
            raise TypeError("database did not return a datetime")
        return value.replace(tzinfo=UTC)


def create_engine(url: str = "sqlite:///lasi.db", **kwargs: Any) -> Engine:
    """Create an engine and enable SQLite foreign-key enforcement."""
    engine = sqlalchemy_create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    """Return a typed session factory bound to *engine*."""
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
