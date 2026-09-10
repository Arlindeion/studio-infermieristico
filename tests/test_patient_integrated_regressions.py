"""Regression gates for the integrated Patients 2.0 P0/P1 fixes.

These tests deliberately avoid importing Flask so the safety-critical service,
pre-deploy and source-shape gates can run even in a lightweight review runtime.
The normal project suite continues to cover the Flask routes when its declared
dependencies are installed.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from patient_cutover_preflight import (
    PAZ_A4_ALEMBIC_REVISION,
    build_patient_cutover_preflight,
)
from patient_data import (
    PatientDataValidationError,
    normalize_email_address,
    normalize_phone_number,
)
from patient_service import (
    AmbiguousPatientMatchError,
    find_active_patient_by_tax_code,
    load_patient_practice_counts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patient_integrated_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codice_fiscale: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dati_anonimizzati_il: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stato: Mapped[str] = mapped_column(String(20), default="attiva")


class Appointment(Base):
    __tablename__ = "appointment_integrated_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SleepCall(Base):
    __tablename__ = "sleep_call_integrated_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Registration(Base):
    __tablename__ = "registration_integrated_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_v2_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    persona_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LegacyLink(Base):
    __tablename__ = "legacy_link_integrated_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entita_tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    entita_id: Mapped[int] = mapped_column(Integer, nullable=False)


def _sqlite_engine():
    return create_engine("sqlite:///:memory:")


def test_shared_contact_validation_matches_persisted_limits():
    assert normalize_email_address("Persona.Test+tag@Example.test") == (
        "persona.test+tag@example.test"
    )
    assert normalize_phone_number("+39 333 000 0000") == "+393330000000"

    with pytest.raises(PatientDataValidationError):
        normalize_email_address(("a" * 90) + "@example.test")
    with pytest.raises(PatientDataValidationError):
        normalize_phone_number("3 3 3 1 2 3 4 5 6 7 8")


def test_tax_code_lookup_never_picks_an_arbitrary_active_duplicate():
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Patient(codice_fiscale="RSSMRA80A01H501X", stato="attiva"),
                Patient(codice_fiscale="RSSMRA80A01H501X", stato="attiva"),
            ]
        )
        session.commit()

        with pytest.raises(AmbiguousPatientMatchError):
            find_active_patient_by_tax_code(
                session,
                Patient,
                "rssmra80a01h501x",
            )


def test_tax_code_lookup_ignores_archived_and_anonymized_rows():
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        expected = Patient(codice_fiscale="RSSMRA80A01H501X", stato="attiva")
        session.add_all(
            [
                expected,
                Patient(codice_fiscale="RSSMRA80A01H501X", stato="archiviata"),
                Patient(
                    codice_fiscale="RSSMRA80A01H501X",
                    stato="attiva",
                    dati_anonimizzati_il="2026-09-10",
                ),
            ]
        )
        session.commit()

        found = find_active_patient_by_tax_code(
            session,
            Patient,
            "RSSMRA80A01H501X",
        )
        assert found.id == expected.id


def test_practice_counts_deduplicate_direct_and_legacy_history():
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        patient = SimpleNamespace(id=10, legacy_persona_corso_id=20)
        second = SimpleNamespace(id=11, legacy_persona_corso_id=None)
        session.add_all(
            [
                Appointment(id=1, persona_id=10),
                SleepCall(id=2, persona_id=10),
                Registration(id=3, persona_v2_id=10, persona_id=20),
                Registration(id=4, persona_v2_id=None, persona_id=20),
                Appointment(id=5, persona_id=11),
                Appointment(id=6, persona_id=None),
                LegacyLink(persona_id=20, entita_tipo="Appuntamento", entita_id=1),
                LegacyLink(persona_id=20, entita_tipo="Appuntamento", entita_id=6),
                LegacyLink(persona_id=20, entita_tipo="Appuntamento", entita_id=999),
                LegacyLink(persona_id=20, entita_tipo="Altro", entita_id=99),
            ]
        )
        session.commit()

        counts = load_patient_practice_counts(
            session,
            [patient, second],
            appointment_model=Appointment,
            sleep_call_model=SleepCall,
            registration_model=Registration,
            legacy_link_model=LegacyLink,
        )

        assert counts == {10: 5, 11: 1}


def test_practice_count_query_volume_does_not_scale_with_patient_count():
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        patients = [
            SimpleNamespace(id=index, legacy_persona_corso_id=None)
            for index in range(1, 101)
        ]
        session.add_all(Appointment(id=index, persona_id=index) for index in range(1, 101))
        session.commit()

        statements: list[str] = []

        def record_statement(*args):
            statements.append(args[2])

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            counts = load_patient_practice_counts(
                session,
                patients,
                appointment_model=Appointment,
                sleep_call_model=SleepCall,
                registration_model=Registration,
                legacy_link_model=LegacyLink,
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    assert len(statements) == 3
    assert len(counts) == 100
    assert all(count == 1 for count in counts.values())


def test_practice_count_query_volume_stays_bounded_with_legacy_links():
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        patients = [
            SimpleNamespace(id=index, legacy_persona_corso_id=1000 + index)
            for index in range(1, 101)
        ]
        session.add_all(
            Registration(
                id=index,
                persona_v2_id=None,
                persona_id=1000 + index,
            )
            for index in range(1, 101)
        )
        session.add_all(
            Appointment(id=2000 + index, persona_id=None)
            for index in range(1, 101)
        )
        session.add_all(
            SleepCall(id=3000 + index, persona_id=None)
            for index in range(1, 101)
        )
        session.add_all(
            LegacyLink(
                persona_id=1000 + index,
                entita_tipo="Appuntamento",
                entita_id=2000 + index,
            )
            for index in range(1, 101)
        )
        session.add_all(
            LegacyLink(
                persona_id=1000 + index,
                entita_tipo="CallSonno",
                entita_id=3000 + index,
            )
            for index in range(1, 101)
        )
        session.commit()

        statements: list[str] = []

        def record_statement(*args):
            statements.append(args[2])

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            counts = load_patient_practice_counts(
                session,
                patients,
                appointment_model=Appointment,
                sleep_call_model=SleepCall,
                registration_model=Registration,
                legacy_link_model=LegacyLink,
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    assert len(statements) == 7
    assert len(counts) == 100
    assert all(count == 3 for count in counts.values())


def _create_pre_a1_schema(engine, revision="d91e6b4f2a30", *, with_row=False):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO alembic_version(version_num) VALUES (?)",
            (revision,),
        )
        for table_name in (
            "appuntamento",
            "call_sonno",
            "iscrizione_corso",
            "collegamento_persona",
            "persona_corso",
        ):
            connection.exec_driver_sql(
                f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY)'
            )
        if revision in {"a6c9e1f4b802", "b7d2e4f6a810", "c9e1f4a7b260"}:
            connection.exec_driver_sql(
                "CREATE TABLE consenso_privacy_paziente (id INTEGER PRIMARY KEY)"
            )
        if with_row:
            connection.exec_driver_sql("INSERT INTO appuntamento(id) VALUES (1)")


@pytest.mark.parametrize("revision", ["d91e6b4f2a30", "b7d2e4f6a810", "c9e1f4a7b260"])
def test_predeploy_preflight_accepts_known_empty_pre_a1_revisions(revision):
    engine = _sqlite_engine()
    _create_pre_a1_schema(engine, revision)

    payload = build_patient_cutover_preflight(engine)

    assert payload["status"] == "pronto"
    assert payload["phase"] == "pre_migration"
    assert payload["alembic_revision"] == revision
    assert payload["target_revision"] == PAZ_A4_ALEMBIC_REVISION
    assert all(count == 0 for count in payload["counts"].values())


def test_predeploy_preflight_blocks_non_empty_database_without_reading_values():
    engine = _sqlite_engine()
    _create_pre_a1_schema(engine, with_row=True)

    payload = build_patient_cutover_preflight(engine)

    assert payload["status"] == "bloccato"
    assert payload["error_code"] == "PAZ_A3_DATABASE_NON_VUOTO"
    assert payload["counts"]["appuntamenti"] == 1


def test_predeploy_preflight_blocks_unexpected_v2_schema_before_a1():
    engine = _sqlite_engine()
    _create_pre_a1_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE persona (id INTEGER PRIMARY KEY)")

    payload = build_patient_cutover_preflight(engine)

    assert payload["status"] == "bloccato"
    assert payload["error_code"] == "PAZ_A3_SCHEMA_INATTESO"
    assert payload["schema_issue"] == "tabelle_v2_inattese"


def _create_a4_schema(engine, *, with_patient=False):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO alembic_version(version_num) VALUES (?)",
            (PAZ_A4_ALEMBIC_REVISION,),
        )
        connection.exec_driver_sql(
            "CREATE TABLE persona (id INTEGER PRIMARY KEY, dati_anonimizzati_il TEXT)"
        )
        for table_name in (
            "recapito_persona",
            "relazione_persona",
            "segnalazione_duplicato",
            "fusione_persona",
            "appuntamento",
            "call_sonno",
            "iscrizione_corso",
            "collegamento_persona",
            "persona_corso",
        ):
            connection.exec_driver_sql(
                f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY)'
            )
        connection.exec_driver_sql(
            "CREATE TABLE consenso_privacy_paziente "
            "(id INTEGER PRIMARY KEY, persona_v2_id INTEGER)"
        )
        if with_patient:
            connection.exec_driver_sql("INSERT INTO persona(id) VALUES (1)")


def test_predeploy_allows_applied_a4_but_strict_diagnostic_still_counts():
    engine = _sqlite_engine()
    _create_a4_schema(engine, with_patient=True)

    deploy_payload = build_patient_cutover_preflight(engine, allow_applied=True)
    strict_payload = build_patient_cutover_preflight(engine)

    assert deploy_payload == {
        "status": "cutover_gia_applicato",
        "alembic_revision": PAZ_A4_ALEMBIC_REVISION,
    }
    assert strict_payload["status"] == "bloccato"
    assert strict_payload["error_code"] == "PAZ_A3_DATABASE_NON_VUOTO"
    assert strict_payload["counts"]["persone_v2"] == 1


def test_a4_downgrade_guard_blocks_even_an_a2_legacy_mapped_identity():
    migration_path = (
        PROJECT_ROOT
        / "migrations"
        / "versions"
        / "d4a7c2e9f610_cutover_pazienti_v2_paz_a4.py"
    )
    spec = importlib.util.spec_from_file_location("a4_integrated_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    engine = _sqlite_engine()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE persona (id INTEGER PRIMARY KEY, legacy_persona_corso_id INTEGER)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE consenso_privacy_paziente (persona_v2_id INTEGER)"
        )
        connection.exec_driver_sql("CREATE TABLE appuntamento (persona_id INTEGER)")
        connection.exec_driver_sql("CREATE TABLE call_sonno (persona_id INTEGER)")
        connection.exec_driver_sql(
            "CREATE TABLE iscrizione_corso (persona_v2_id INTEGER)"
        )
        assert migration._has_a4_writes(connection) is False
        connection.exec_driver_sql(
            "INSERT INTO persona(id, legacy_persona_corso_id) VALUES (1, 10)"
        )
        assert migration._has_a4_writes(connection) is True


def _function_source(tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"function {name} not found")


def test_every_confirmation_surface_contains_the_v2_link_gate():
    tree = ast.parse((PROJECT_ROOT / "app.py").read_text())

    slot = _function_source(tree, "accetta_proposta_slot")
    assert "_ensure_patient_for_appointment" in slot
    assert "_ensure_patient_for_sleep_call" in slot
    assert "_audit_automatic_patient_link" in slot

    direct_call = _function_source(tree, "conferma_call_sonno_admin")
    edit_call = _function_source(tree, "modifica_call_sonno_admin")
    assert "_ensure_patient_for_sleep_call" in direct_call
    assert "_ensure_patient_for_sleep_call" in edit_call

    direct_appointment = _function_source(tree, "aggiorna_stato")
    edit_appointment = _function_source(tree, "modifica_appuntamento")
    assert "_ensure_patient_for_appointment" in direct_appointment
    assert "_ensure_patient_for_appointment" in edit_appointment

    course_status = _function_source(tree, "aggiorna_stato_iscrizione_corso")
    public_course = _function_source(tree, "iscrizione_corso")
    assert "_ensure_patient_for_course_registration" in course_status
    assert "AmbiguousPatientMatchError" in course_status
    assert "AmbiguousPatientMatchError" in public_course


def test_render_predeploy_runs_preflight_before_migrations_and_db_check():
    source = (PROJECT_ROOT / "render.production.yaml").read_text()
    line = next(
        item.strip()
        for item in source.splitlines()
        if item.strip().startswith("preDeployCommand:")
    )
    preflight = line.index("python patient_cutover_preflight.py --allow-applied")
    upgrade = line.index("flask --app app db upgrade")
    db_check = line.index("flask --app app db check")
    bootstrap = line.index("flask --app app bootstrap-admin")
    assert preflight < upgrade < db_check < bootstrap


def test_public_contact_fields_match_backend_limits_and_shared_validators():
    app_source = (PROJECT_ROOT / "app.py").read_text()
    tree = ast.parse(app_source)
    email_validator = _function_source(tree, "_email_valida")
    phone_validator = _function_source(tree, "_telefono_valido")
    assert "normalize_email_address" in email_validator
    assert "normalize_phone_number" in phone_validator

    public_templates = [
        PROJECT_ROOT / "templates" / "prenota.html",
        PROJECT_ROOT / "templates" / "iscrizione_corso.html",
        PROJECT_ROOT / "templates" / "iscrizione_accompagnamento_privata.html",
        PROJECT_ROOT / "templates" / "richiesta_azienda.html",
        PROJECT_ROOT / "templates" / "interesse_corsi.html",
        PROJECT_ROOT / "templates" / "prenota_call_sonno.html",
    ]
    for path in public_templates:
        source = path.read_text()
        assert 'name="telefono"' in source
        assert 'maxlength="20"' in source
        assert 'pattern="[0-9+()./ \\-]{6,20}"' in source

    email_templates = public_templates[:3] + public_templates[3:]
    for path in email_templates:
        source = path.read_text()
        assert 'name="email"' in source
        assert 'maxlength="100"' in source


def test_python_naming_exception_is_explicit_and_new_patient_modules_use_english_api():
    agents = (PROJECT_ROOT / "AGENTS.md").read_text()
    assert "Eccezione transitoria Pazienti 2.0" in agents
    assert "ogni nuovo modulo o API Python deve usare nomi inglesi" in agents

    service_source = (PROJECT_ROOT / "patient_service.py").read_text()
    preflight_source = (PROJECT_ROOT / "patient_cutover_preflight.py").read_text()
    assert "def find_active_patient_by_tax_code" in service_source
    assert "def load_patient_practice_counts" in service_source
    assert "def build_patient_cutover_preflight" in preflight_source
