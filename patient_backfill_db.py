"""Database lock/transaction adapters for PAZ-A2.

The service layer owns validation and reconciliation. This module owns only the
cross-database rule that one apply must run under one write transaction and one
exclusive A2 lock.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


class ConcurrentApplyLockError(Exception):
    pass


class UnsupportedBackfillDialectError(Exception):
    pass


@contextmanager
def _sqlite_apply_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    session: Session | None = None
    try:
        connection.exec_driver_sql("PRAGMA busy_timeout = 1")
        try:
            # Must happen before any ORM operation starts an implicit transaction.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            raise ConcurrentApplyLockError() from exc
        session = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="control_fully",
        )
        yield session
    except Exception:
        if session is not None:
            session.rollback()
        elif connection.in_transaction():
            connection.rollback()
        raise
    finally:
        if session is not None:
            session.close()
        connection.close()


@contextmanager
def _postgres_apply_session(engine: Engine, advisory_lock_key: int) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="control_fully",
    )
    try:
        locked = bool(
            session.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                {"lock_key": advisory_lock_key},
            ).scalar_one()
        )
        if not locked:
            raise ConcurrentApplyLockError()

        session.execute(text("LOCK TABLE persona_corso IN SHARE MODE"))
        session.execute(text("LOCK TABLE persona, recapito_persona IN SHARE ROW EXCLUSIVE MODE"))
        session.execute(
            text(
                "LOCK TABLE appuntamento, call_sonno, iscrizione_corso, "
                "relazione_persona, segnalazione_duplicato, fusione_persona IN SHARE MODE"
            )
        )
        yield session
    except Exception:
        if session.is_active:
            session.rollback()
        elif transaction.is_active:
            transaction.rollback()
        raise
    finally:
        session.close()
        connection.close()


@contextmanager
def apply_session(engine: Engine, advisory_lock_key: int) -> Iterator[Session]:
    if engine.dialect.name == "sqlite":
        with _sqlite_apply_session(engine) as session:
            yield session
        return
    if engine.dialect.name == "postgresql":
        with _postgres_apply_session(engine, advisory_lock_key) as session:
            yield session
        return
    raise UnsupportedBackfillDialectError(engine.dialect.name)
