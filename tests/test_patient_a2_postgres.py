from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import patient_backfill as pb
from patient_backfill import ConcurrentBackfillError, apply_backfill_plan, build_backfill_plan
from tests.test_patient_a2_backfill import (
    A1_REVISION,
    CODE_REVISION,
    MODELS,
    NOW,
    Persona,
    RecapitoPersona,
    add_source,
)


POSTGRES_URL = os.environ.get("PAZ_A2_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="PAZ_A2_TEST_DATABASE_URL non configurata per il database PostgreSQL usa-e-getta.",
)


def _normalize_postgres_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


def _with_search_path(raw: str, schema: str) -> str:
    url = make_url(_normalize_postgres_url(raw))
    query = dict(url.query)
    query["options"] = f"-csearch_path={schema}"
    return url.set(query=query).render_as_string(hide_password=False)




def _probe_flask_database(project_root: Path, database_url: str, expected_schema: str) -> str:
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.update(
        {
            "FLASK_ENV": "paz_a2_postgres_testing",
            "APP_ENV": "testing",
            "SECRET_KEY": "p" * 64,
            "PAZ_A2_TEST_DATABASE_URL": database_url,
            "APP_BUILD_REVISION": CODE_REVISION,
            "MAIL_SUPPRESS_SEND": "true",
        }
    )
    script = (
        "from app import app, db; from sqlalchemy import text; "
        "ctx=app.app_context(); ctx.push(); "
        "print(db.engine.dialect.name); "
        "print(db.session.execute(text('SELECT current_schema()')).scalar_one()); "
        "ctx.pop()"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    assert "postgresql" in lines
    assert expected_schema in lines
    return completed.stdout
def _run_flask_db(project_root: Path, database_url: str, command: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.update(
        {
            "FLASK_ENV": "paz_a2_postgres_testing",
            "APP_ENV": "testing",
            "SECRET_KEY": "p" * 64,
            "PAZ_A2_TEST_DATABASE_URL": database_url,
            "APP_BUILD_REVISION": CODE_REVISION,
            "MAIL_SUPPRESS_SEND": "true",
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "flask", "--app", "app", "db", command],
        cwd=project_root,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="module")
def postgres_runtime():
    base_url = _normalize_postgres_url(POSTGRES_URL)
    admin_engine = create_engine(base_url, future=True)
    schema = f"paz_a2_{uuid.uuid4().hex[:12]}"
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_url = _with_search_path(base_url, schema)
    project_root = Path(__file__).resolve().parents[1]
    try:
        _probe_flask_database(project_root, test_url, schema)
        upgrade = _run_flask_db(project_root, test_url, "upgrade")
        assert upgrade.returncode == 0
        check = _run_flask_db(project_root, test_url, "check")
        assert "No new upgrade operations detected" in check.stdout
        engine = create_engine(test_url, future=True)
        yield engine, test_url, project_root
        engine.dispose()
    finally:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _config():
    return {
        "SECRET_KEY": "p" * 64,
        "SECRET_KEY_IS_EPHEMERAL": False,
        "APP_ENV": "testing",
        "PAZ_A2_PLAN_TTL_SECONDS": 3600,
        "APP_BUILD_REVISION": CODE_REVISION,
    }


def test_postgres_real_apply_and_db_check(postgres_runtime):
    engine, test_url, project_root = postgres_runtime
    with Session(engine) as session:
        add_source(session, nome="Postgres Persona", telefono="3334445555", email="pg@example.test")
        session.commit()

    config = _config()
    with Session(engine) as session:
        plan = build_backfill_plan(
            session,
            MODELS,
            engine=engine,
            config=config,
            now=NOW,
            code_revision=CODE_REVISION,
        )
    result = apply_backfill_plan(
        engine,
        MODELS,
        plan,
        config=config,
        now=NOW + timedelta(minutes=1),
        code_revision=CODE_REVISION,
    )
    assert result.actions == {"create": 1}
    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 1
        assert session.scalar(select(pb.func.count()).select_from(RecapitoPersona)) == 2

    check = _run_flask_db(project_root, test_url, "check")
    assert "No new upgrade operations detected" in check.stdout


def test_postgres_second_a2_writer_cannot_acquire_advisory_lock(postgres_runtime):
    engine, _test_url, _project_root = postgres_runtime
    acquired = threading.Event()
    release = threading.Event()

    def holder():
        with pb.apply_session(engine):
            acquired.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert acquired.wait(timeout=3)
    try:
        with pytest.raises(ConcurrentBackfillError):
            with pb.apply_session(engine):
                pass
    finally:
        release.set()
        thread.join(timeout=5)


def test_postgres_source_table_is_frozen_during_apply_lock(postgres_runtime):
    engine, _test_url, _project_root = postgres_runtime
    with pb.apply_session(engine):
        with engine.connect() as contender:
            transaction = contender.begin()
            try:
                contender.execute(text("SET LOCAL lock_timeout = '150ms'"))
                with pytest.raises(OperationalError):
                    contender.execute(
                        text(
                            "INSERT INTO persona_corso "
                            "(nome, creato_il, aggiornato_il) "
                            "VALUES ('Concurrent', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                        )
                    )
            finally:
                transaction.rollback()
