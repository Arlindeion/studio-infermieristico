"""Real PostgreSQL acceptance tests for PAZ-A1.

These tests are intentionally opt-in because they create and drop an isolated
schema. Set ``PAZ_A1_POSTGRES_URL`` to a disposable/test PostgreSQL database.
They are not satisfied by SQL compilation alone.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import threading
import time
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / 'migrations' / 'versions'
A1_REVISION = '8f2c7d1e4a90'
POSTGRES_URL = os.environ.get('PAZ_A1_POSTGRES_URL')

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason='PAZ_A1_POSTGRES_URL non configurato: prova PostgreSQL reale non eseguita.',
)


def _revision_metadata(path):
    tree = ast.parse(path.read_text())
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {'revision', 'down_revision'}:
                values[target.id] = ast.literal_eval(node.value)
    return values


def _migration_files():
    result = {}
    for path in MIGRATIONS_DIR.glob('*.py'):
        metadata = _revision_metadata(path)
        revision = metadata.get('revision')
        if revision:
            result[revision] = (path, metadata.get('down_revision'))
    return result


def _chain_to(revision):
    files = _migration_files()
    chain = []
    current = revision
    while current:
        path, parent = files[current]
        chain.append((current, path))
        current = parent
    return list(reversed(chain))


def _load_migration(revision, path):
    spec = importlib.util.spec_from_file_location(f'pg_test_migration_{revision}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_search_path(connection, schema):
    connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')


@pytest.fixture(scope='module')
def postgres_a1():
    engine = sa.create_engine(POSTGRES_URL, pool_pre_ping=True)
    schema = f'paz_a1_{uuid.uuid4().hex[:12]}'

    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        _set_search_path(connection, schema)
        context = MigrationContext.configure(connection)
        for revision, path in _chain_to(A1_REVISION):
            module = _load_migration(revision, path)
            with Operations.context(context):
                module.upgrade()

    try:
        yield engine, schema
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        engine.dispose()


def test_postgres_full_chain_and_restrict_fk(postgres_a1):
    engine, schema = postgres_a1
    with engine.begin() as connection:
        _set_search_path(connection, schema)
        inspector = sa.inspect(connection)
        assert {'persona', 'recapito_persona', 'relazione_persona'} <= set(inspector.get_table_names())

        legacy_id = connection.execute(
            sa.text("INSERT INTO persona_corso (nome) VALUES ('Legacy PostgreSQL') RETURNING id")
        ).scalar_one()
        connection.execute(
            sa.text("""
                INSERT INTO persona (nome, stato, legacy_persona_corso_id)
                VALUES ('Persona PostgreSQL', 'attiva', :legacy)
            """),
            {'legacy': legacy_id},
        )
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    sa.text('DELETE FROM persona_corso WHERE id = :legacy'),
                    {'legacy': legacy_id},
                )


def test_postgres_partial_unique_index_enforces_single_primary(postgres_a1):
    engine, schema = postgres_a1
    with engine.begin() as connection:
        _set_search_path(connection, schema)
        person_id = connection.execute(
            sa.text("INSERT INTO persona (nome, stato) VALUES ('Primary PG', 'attiva') RETURNING id")
        ).scalar_one()
        connection.execute(
            sa.text("""
                INSERT INTO recapito_persona
                    (persona_id, tipo, valore, valore_normalizzato, principale)
                VALUES (:person, 'telefono', '3331111111', '3331111111', true)
            """),
            {'person': person_id},
        )
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    sa.text("""
                        INSERT INTO recapito_persona
                            (persona_id, tipo, valore, valore_normalizzato, principale)
                        VALUES (:person, 'telefono', '3332222222', '3332222222', true)
                    """),
                    {'person': person_id},
                )


def test_postgres_concurrent_primary_inserts_cannot_both_commit(postgres_a1):
    engine, schema = postgres_a1
    with engine.begin() as setup:
        _set_search_path(setup, schema)
        person_id = setup.execute(
            sa.text("INSERT INTO persona (nome, stato) VALUES ('Concurrent PG', 'attiva') RETURNING id")
        ).scalar_one()

    first_ready = threading.Event()
    second_attempting_insert = threading.Event()
    allow_first_commit = threading.Event()
    second_pid = {}
    results = []

    def first_writer():
        connection = engine.connect()
        transaction = connection.begin()
        try:
            _set_search_path(connection, schema)
            connection.execute(
                sa.text("""
                    INSERT INTO recapito_persona
                        (persona_id, tipo, valore, valore_normalizzato, principale)
                    VALUES (:person, 'email', 'first@example.invalid', 'first@example.invalid', true)
                """),
                {'person': person_id},
            )
            first_ready.set()
            assert allow_first_commit.wait(timeout=10)
            transaction.commit()
            results.append('first-committed')
        finally:
            connection.close()

    def second_writer():
        assert first_ready.wait(timeout=10)
        connection = engine.connect()
        transaction = connection.begin()
        try:
            _set_search_path(connection, schema)
            connection.exec_driver_sql("SET LOCAL statement_timeout = '8s'")
            second_pid['value'] = connection.execute(
                sa.text('SELECT pg_backend_pid()')
            ).scalar_one()
            second_attempting_insert.set()
            try:
                connection.execute(
                    sa.text("""
                        INSERT INTO recapito_persona
                            (persona_id, tipo, valore, valore_normalizzato, principale)
                        VALUES (:person, 'email', 'second@example.invalid', 'second@example.invalid', true)
                    """),
                    {'person': person_id},
                )
                transaction.commit()
                results.append('second-committed')
            except IntegrityError:
                transaction.rollback()
                results.append('second-rejected')
        finally:
            connection.close()

    t1 = threading.Thread(target=first_writer, daemon=True)
    t2 = threading.Thread(target=second_writer, daemon=True)
    t1.start()
    t2.start()
    assert first_ready.wait(timeout=10)
    assert second_attempting_insert.wait(timeout=10)

    deadline = time.monotonic() + 10
    second_is_waiting_on_lock = False
    with engine.connect() as observer:
        while time.monotonic() < deadline:
            wait_event_type = observer.execute(
                sa.text(
                    'SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid'
                ),
                {'pid': second_pid['value']},
            ).scalar_one_or_none()
            if wait_event_type == 'Lock':
                second_is_waiting_on_lock = True
                break
            time.sleep(0.05)

    assert second_is_waiting_on_lock
    allow_first_commit.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive()
    assert not t2.is_alive()
    assert sorted(results) == ['first-committed', 'second-rejected']

    with engine.begin() as connection:
        _set_search_path(connection, schema)
        count = connection.execute(
            sa.text("""
                SELECT COUNT(*) FROM recapito_persona
                WHERE persona_id = :person AND tipo = 'email'
                  AND principale IS TRUE AND archiviato_il IS NULL
            """),
            {'person': person_id},
        ).scalar_one()
        assert count == 1
