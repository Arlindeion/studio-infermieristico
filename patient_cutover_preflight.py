"""Read-only pre-migration gate for the Patients 2.0 cutover.

Render runs this module before Alembic.  It deliberately does not import the
Flask application or its ORM models, so the first cutover can verify the
currently deployed pre-A1 database before any migration writes occur.  Only the
Alembic revision, schema metadata and aggregate row counts are read; no patient
values are selected or printed.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


PAZ_A4_ALEMBIC_REVISION = "d4a7c2e9f610"
PRE_A1_DEPLOY_REVISIONS = (
    "d91e6b4f2a30",
    "e2f4a6b8c901",
    "f4c8a2d7e901",
    "a6c9e1f4b802",
    "b7d2e4f6a810",
    "c9e1f4a7b260",
)

COUNT_TABLES = (
    ("appuntamenti", "appuntamento"),
    ("call_sonno", "call_sonno"),
    ("consensi_privacy_paziente", "consenso_privacy_paziente"),
    ("iscrizioni_corso", "iscrizione_corso"),
    ("collegamenti_legacy", "collegamento_persona"),
    ("persone_legacy", "persona_corso"),
    ("persone_v2", "persona"),
)

PRE_A1_REQUIRED_TABLES = frozenset(
    {
        "alembic_version",
        "appuntamento",
        "call_sonno",
        "iscrizione_corso",
        "collegamento_persona",
        "persona_corso",
    }
)

PATIENTS_V2_TABLES = frozenset(
    {
        "persona",
        "recapito_persona",
        "relazione_persona",
        "segnalazione_duplicato",
        "fusione_persona",
    }
)


def normalize_database_url(database_url: str | None) -> str | None:
    """Normalize Render PostgreSQL URLs without importing application config."""

    if not database_url:
        return None
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _blocked(error_code: str, revision: str | None = None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "bloccato",
        "error_code": error_code,
        "alembic_revision": revision,
    }
    payload.update(extra)
    return payload


def _read_alembic_revision(connection) -> str | None:
    rows = connection.execute(
        text("SELECT version_num FROM alembic_version ORDER BY version_num")
    ).scalars().all()
    if len(rows) != 1 or not rows[0]:
        return None
    return str(rows[0])


def _count_rows(connection, available_tables: set[str], table_name: str) -> int:
    if table_name not in available_tables:
        return 0
    # table_name is selected only from COUNT_TABLES above; no user input is SQL.
    return int(
        connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
    )


def _a4_schema_is_complete(connection, available_tables: set[str]) -> bool:
    if not PATIENTS_V2_TABLES <= available_tables:
        return False
    if "consenso_privacy_paziente" not in available_tables:
        return False
    inspector = inspect(connection)
    persona_columns = {column["name"] for column in inspector.get_columns("persona")}
    consent_columns = {
        column["name"]
        for column in inspector.get_columns("consenso_privacy_paziente")
    }
    return (
        "dati_anonimizzati_il" in persona_columns
        and "persona_v2_id" in consent_columns
    )


def build_patient_cutover_preflight(
    engine: Engine,
    *,
    allow_applied: bool = False,
) -> dict[str, Any]:
    """Return a PII-free report without performing writes.

    ``allow_applied`` is for the persistent Render pre-deploy hook.  It permits
    later normal deploys once A4 is already the actual database revision, but it
    never bypasses the empty-database check during the first pre-A1 cutover.
    """

    try:
        with engine.connect() as connection:
            available_tables = set(inspect(connection).get_table_names())
            if "alembic_version" not in available_tables:
                return _blocked("PAZ_A3_REVISIONE_NON_VERIFICABILE")

            revision = _read_alembic_revision(connection)
            if revision is None:
                return _blocked("PAZ_A3_REVISIONE_NON_VERIFICABILE")

            if revision == PAZ_A4_ALEMBIC_REVISION:
                if not _a4_schema_is_complete(connection, available_tables):
                    return _blocked(
                        "PAZ_A3_SCHEMA_INATTESO",
                        revision,
                        schema_issue="a4_incompleto",
                    )
                if allow_applied:
                    return {
                        "status": "cutover_gia_applicato",
                        "alembic_revision": revision,
                    }
            elif revision in PRE_A1_DEPLOY_REVISIONS:
                missing_core_tables = PRE_A1_REQUIRED_TABLES - available_tables
                unexpected_v2_tables = PATIENTS_V2_TABLES & available_tables
                if missing_core_tables or unexpected_v2_tables:
                    return _blocked(
                        "PAZ_A3_SCHEMA_INATTESO",
                        revision,
                        schema_issue=(
                            "tabelle_core_mancanti"
                            if missing_core_tables
                            else "tabelle_v2_inattese"
                        ),
                        table_count=len(missing_core_tables or unexpected_v2_tables),
                    )
            else:
                return _blocked(
                    "PAZ_A3_REVISIONE_NON_VALIDA",
                    revision,
                    expected_revision=PAZ_A4_ALEMBIC_REVISION,
                )

            counts = {
                label: _count_rows(connection, available_tables, table_name)
                for label, table_name in COUNT_TABLES
            }
    except Exception:
        return _blocked("PAZ_A3_PREFLIGHT_NON_ESEGUIBILE")

    non_empty = {key: value for key, value in counts.items() if value}
    payload: dict[str, Any] = {
        "status": "bloccato" if non_empty else "pronto",
        "alembic_revision": revision,
        "counts": counts,
    }
    if revision in PRE_A1_DEPLOY_REVISIONS:
        payload["phase"] = "pre_migration"
        payload["target_revision"] = PAZ_A4_ALEMBIC_REVISION
    if non_empty:
        payload["error_code"] = "PAZ_A3_DATABASE_NON_VUOTO"
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Patients 2.0 pre-deploy cutover gate."
    )
    parser.add_argument(
        "--allow-applied",
        action="store_true",
        help="Permit later deploys when A4 is already applied.",
    )
    args = parser.parse_args(argv)

    database_url = normalize_database_url(os.environ.get("DATABASE_URL"))
    if not database_url:
        print(json.dumps(_blocked("PAZ_A3_DATABASE_URL_MANCANTE"), sort_keys=True))
        return 2

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        payload = build_patient_cutover_preflight(
            engine,
            allow_applied=args.allow_applied,
        )
    finally:
        engine.dispose()

    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] in {"pronto", "cutover_gia_applicato"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
