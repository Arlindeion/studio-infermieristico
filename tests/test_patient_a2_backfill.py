from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import threading
import time

import pytest
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

import patient_backfill as pb
from patient_backfill import (
    BackfillBlockerError,
    BackfillModels,
    ConcurrentBackfillError,
    ExpiredPlanError,
    InvalidPlanError,
    StalePlanError,
    StaleTargetError,
    analyze_legacy_source,
    apply_backfill_plan,
    build_backfill_plan,
    canonical_json_bytes,
    database_environment_fingerprint,
    dry_run_result,
    get_plan_key,
    read_plan_file_secure,
    sign_plan,
    validate_plan_schema,
    verify_plan_signature,
    write_plan_file,
)
from patient_data import ANONYMIZED_PERSON_PLACEHOLDER


NOW = datetime(2026, 9, 7, 12, 0, 0)
A1_REVISION = "8f2c7d1e4a90"
CODE_REVISION = "ebab09b-test"
SENTINEL_NAME = "PII_SENTINEL_NAME_7f2b"
SENTINEL_PHONE = "+39 333 123 4567"
SENTINEL_EMAIL = "pii-sentinel@example.test"
SENTINEL_NOTE = "PII_SENTINEL_NOTE_7f2b"
SENTINEL_CHILD = "PII_SENTINEL_CHILD_7f2b"


class Base(DeclarativeBase):
    pass


class PersonaCorso(Base):
    __tablename__ = "persona_corso"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(100))
    codice_fiscale: Mapped[str | None] = mapped_column(String(32))
    nome_bambino: Mapped[str | None] = mapped_column(String(100))
    eta_bambino: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)
    creato_il: Mapped[datetime | None] = mapped_column(DateTime)
    aggiornato_il: Mapped[datetime | None] = mapped_column(DateTime)
    dati_anonimizzati_il: Mapped[datetime | None] = mapped_column(DateTime)


class Persona(Base):
    __tablename__ = "persona"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str | None] = mapped_column(String(100))
    cognome: Mapped[str | None] = mapped_column(String(100))
    data_nascita: Mapped[datetime | None] = mapped_column(Date)
    sesso_anagrafico: Mapped[str | None] = mapped_column(String(1))
    codice_fiscale: Mapped[str | None] = mapped_column(String(32))
    comune_nascita: Mapped[str | None] = mapped_column(String(120))
    provincia_nascita: Mapped[str | None] = mapped_column(String(10))
    stato_nascita: Mapped[str | None] = mapped_column(String(120))
    indirizzo_residenza: Mapped[str | None] = mapped_column(String(200))
    cap_residenza: Mapped[str | None] = mapped_column(String(12))
    comune_residenza: Mapped[str | None] = mapped_column(String(120))
    provincia_residenza: Mapped[str | None] = mapped_column(String(10))
    stato_residenza: Mapped[str | None] = mapped_column(String(120))
    stato: Mapped[str] = mapped_column(String(20), default="attiva")
    anagrafica_da_verificare: Mapped[bool] = mapped_column(Boolean, default=False)
    legacy_persona_corso_id: Mapped[int | None] = mapped_column(
        ForeignKey("persona_corso.id", ondelete="RESTRICT"), unique=True
    )
    legacy_nome_completo: Mapped[str | None] = mapped_column(String(200))
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=lambda: NOW)
    aggiornato_il: Mapped[datetime] = mapped_column(DateTime, default=lambda: NOW)
    archiviato_il: Mapped[datetime | None] = mapped_column(DateTime)
    recapiti: Mapped[list["RecapitoPersona"]] = relationship(back_populates="persona")


class RecapitoPersona(Base):
    __tablename__ = "recapito_persona"
    __table_args__ = (
        UniqueConstraint("persona_id", "tipo", "valore_normalizzato", name="uq_recapito_persona_valore"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.id", ondelete="RESTRICT"))
    tipo: Mapped[str] = mapped_column(String(20))
    valore: Mapped[str] = mapped_column(String(254))
    valore_normalizzato: Mapped[str] = mapped_column(String(254))
    principale: Mapped[bool] = mapped_column(Boolean, default=False)
    etichetta: Mapped[str | None] = mapped_column(String(80))
    creato_il: Mapped[datetime] = mapped_column(DateTime, default=lambda: NOW)
    archiviato_il: Mapped[datetime | None] = mapped_column(DateTime)
    persona: Mapped[Persona] = relationship(back_populates="recapiti")


class RelazionePersona(Base):
    __tablename__ = "relazione_persona"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_assistita_id: Mapped[int | None] = mapped_column(Integer)


class SegnalazioneDuplicato(Base):
    __tablename__ = "segnalazione_duplicato"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class FusionePersona(Base):
    __tablename__ = "fusione_persona"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class Appuntamento(Base):
    __tablename__ = "appuntamento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int | None] = mapped_column(Integer)


class CallSonno(Base):
    __tablename__ = "call_sonno"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int | None] = mapped_column(Integer)


class IscrizioneCorso(Base):
    __tablename__ = "iscrizione_corso"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_v2_id: Mapped[int | None] = mapped_column(Integer)


class RegistroEvento(Base):
    __tablename__ = "registro_evento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria: Mapped[str] = mapped_column(String(40))
    esito: Mapped[str] = mapped_column(String(20))
    messaggio: Mapped[str] = mapped_column(Text)
    entita_tipo: Mapped[str | None] = mapped_column(String(80))
    entita_id: Mapped[int | None] = mapped_column(Integer)
    dettagli: Mapped[str | None] = mapped_column(Text)
    creato_il: Mapped[datetime] = mapped_column(DateTime)
    risolto_il: Mapped[datetime | None] = mapped_column(DateTime)
    nota_risoluzione: Mapped[str | None] = mapped_column(Text)


MODELS = BackfillModels(
    PersonaCorso=PersonaCorso,
    Persona=Persona,
    RecapitoPersona=RecapitoPersona,
    RelazionePersona=RelazionePersona,
    SegnalazioneDuplicato=SegnalazioneDuplicato,
    FusionePersona=FusionePersona,
    Appuntamento=Appuntamento,
    CallSonno=CallSonno,
    IscrizioneCorso=IscrizioneCorso,
    RegistroEvento=RegistroEvento,
)


@pytest.fixture
def config():
    return {
        "SECRET_KEY": "s" * 64,
        "SECRET_KEY_IS_EPHEMERAL": False,
        "APP_ENV": "testing",
        "PAZ_A2_PLAN_TTL_SECONDS": 3600,
        "APP_BUILD_REVISION": CODE_REVISION,
    }


@pytest.fixture
def engine(tmp_path):
    path = tmp_path / "a2.sqlite"
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql(
            "INSERT INTO alembic_version(version_num) VALUES (?)",
            (A1_REVISION,),
        )
    yield engine
    engine.dispose()


def add_source(session, **overrides):
    values = {
        "nome": SENTINEL_NAME,
        "telefono": SENTINEL_PHONE,
        "email": SENTINEL_EMAIL,
        "codice_fiscale": "RSSMRA80A01H501U",
        "nome_bambino": None,
        "eta_bambino": None,
        "note": None,
        "creato_il": NOW - timedelta(days=10),
        "aggiornato_il": NOW - timedelta(days=1),
        "dati_anonimizzati_il": None,
    }
    values.update(overrides)
    row = PersonaCorso(**values)
    session.add(row)
    session.flush()
    return row


def build_plan(engine, config, *, now=NOW):
    with Session(engine) as session:
        return build_backfill_plan(
            session,
            MODELS,
            engine=engine,
            config=config,
            now=now,
            code_revision=CODE_REVISION,
        )


def test_canonical_json_is_stable():
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_plan_key_rejects_ephemeral(config):
    config["SECRET_KEY_IS_EPHEMERAL"] = True
    with pytest.raises(pb.PatientBackfillError, match="UNSTABLE_PLAN_KEY"):
        get_plan_key(config)


def test_plan_signature_covers_whole_plan(config):
    key = get_plan_key(config)
    unsigned = {"a": 1, "nested": {"x": 2}}
    signature = sign_plan(unsigned, key)
    plan = dict(unsigned, plan_signature=signature)
    verify_plan_signature(plan, key)
    plan["nested"]["x"] = 3
    with pytest.raises(InvalidPlanError):
        verify_plan_signature(plan, key)


def test_database_fingerprint_does_not_depend_on_credentials(config, tmp_path):
    key = get_plan_key(config)

    class DummyEngine:
        def __init__(self, url):
            self.url = make_url(url)

    a = DummyEngine("postgresql://alice:secret@db.example.test:5432/studio")
    b = DummyEngine("postgresql://bob:other@db.example.test:5432/studio")
    assert database_environment_fingerprint(a, "testing", key) == database_environment_fingerprint(b, "testing", key)


def test_anonymized_source_with_residual_pii_is_blocked():
    source = type(
        "S",
        (),
        {
            "id": 1,
            "nome": ANONYMIZED_PERSON_PLACEHOLDER,
            "telefono": "3331234567",
            "email": None,
            "codice_fiscale": None,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": NOW - timedelta(days=1),
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert "ANONYMIZED_SOURCE_HAS_RESIDUAL_PII" in assessment.blockers


def test_placeholder_without_timestamp_is_blocked():
    source = type(
        "S",
        (),
        {
            "id": 1,
            "nome": ANONYMIZED_PERSON_PLACEHOLDER,
            "telefono": None,
            "email": None,
            "codice_fiscale": None,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": None,
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert "ANONYMIZATION_STATE_INCONSISTENT" in assessment.blockers


def test_dry_run_writes_nothing_and_contains_no_pii(engine, config):
    with Session(engine) as session:
        add_source(
            session,
            note=SENTINEL_NOTE,
            nome_bambino=SENTINEL_CHILD,
            eta_bambino="12 mesi",
        )
        session.commit()
        before_people = session.scalar(select(pb.func.count()).select_from(Persona))
        before_contacts = session.scalar(select(pb.func.count()).select_from(RecapitoPersona))

    plan = build_plan(engine, config)
    serialized = json.dumps(plan, ensure_ascii=False)
    for sentinel in (SENTINEL_NAME, SENTINEL_PHONE, SENTINEL_EMAIL, SENTINEL_NOTE, SENTINEL_CHILD, "3331234567"):
        assert sentinel not in serialized

    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == before_people == 0
        assert session.scalar(select(pb.func.count()).select_from(RecapitoPersona)) == before_contacts == 0

    record = plan["records"][0]
    assert "LEGACY_NOTE_PRESENT" in record["warnings"]
    assert "LEGACY_CHILD_FIELDS_PRESENT" in record["warnings"]
    assert record["action"] == "create"


def test_plan_schema_rejects_unknown_field(engine, config):
    plan = build_plan(engine, config)
    plan["unexpected"] = True
    with pytest.raises(InvalidPlanError):
        validate_plan_schema(plan)


def test_plan_schema_rejects_bool_as_legacy_id(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    plan["records"][0]["legacy_id"] = True
    with pytest.raises(InvalidPlanError):
        validate_plan_schema(plan)


def test_secure_plan_file_permissions_and_tamper(tmp_path, engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    path = tmp_path / "paz-a2-plan.json"
    write_plan_file(path, plan)
    assert stat_mode(path) & 0o077 == 0
    loaded = read_plan_file_secure(path)
    assert loaded["plan_signature"] == plan["plan_signature"]

    data = json.loads(path.read_text())
    data["source_count"] += 1
    path.write_text(json.dumps(data))
    os.chmod(path, 0o600)
    with pytest.raises(InvalidPlanError):
        read_plan_file_secure(path)


def stat_mode(path: Path) -> int:
    return os.stat(path).st_mode


def test_secure_plan_file_rejects_symlink(tmp_path, engine, config):
    plan = build_plan(engine, config)
    target = tmp_path / "target.json"
    target.write_text("{}")
    os.chmod(target, 0o600)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(pb.PatientBackfillError):
        write_plan_file(link, plan, overwrite=True)
    with pytest.raises(InvalidPlanError):
        read_plan_file_secure(link)


def test_apply_creates_mapping_contacts_and_atomic_audit(engine, config):
    with Session(engine) as session:
        source = add_source(session)
        legacy_id = source.id
        session.commit()

    plan = build_plan(engine, config)
    result = apply_backfill_plan(
        engine,
        MODELS,
        plan,
        config=config,
        now=NOW + timedelta(minutes=5),
        code_revision=CODE_REVISION,
    )
    assert result.status == "successo"
    assert result.actions == {"create": 1}

    with Session(engine) as session:
        person = session.scalar(select(Persona).where(Persona.legacy_persona_corso_id == legacy_id))
        assert person is not None
        assert person.nome is None and person.cognome is None
        assert person.legacy_nome_completo == SENTINEL_NAME
        assert person.codice_fiscale == "RSSMRA80A01H501U"
        assert person.anagrafica_da_verificare is True
        contacts = session.scalars(select(RecapitoPersona).where(RecapitoPersona.persona_id == person.id)).all()
        assert {contact.tipo for contact in contacts} == {"telefono", "email"}
        assert all(contact.principale for contact in contacts)
        event_row = session.scalar(select(RegistroEvento).where(RegistroEvento.esito == "successo"))
        assert event_row is not None
        serialized_audit = event_row.dettagli or ""
        assert SENTINEL_NAME not in serialized_audit
        assert SENTINEL_PHONE not in serialized_audit
        assert SENTINEL_EMAIL not in serialized_audit
        assert session.scalar(select(pb.func.count()).select_from(Appuntamento).where(Appuntamento.persona_id.is_not(None))) == 0


def test_old_write_plan_becomes_stale_target_after_apply(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    with pytest.raises(StaleTargetError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=2), code_revision=CODE_REVISION)


def test_new_plan_is_idempotent_and_preserves_updated_at(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    first = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, first, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    with Session(engine) as session:
        person = session.scalar(select(Persona))
        original_updated_at = person.aggiornato_il
        original_id = person.id
        contact_ids = tuple(session.scalars(select(RecapitoPersona.id).order_by(RecapitoPersona.id)).all())

    second = build_plan(engine, config, now=NOW + timedelta(minutes=2))
    assert second["records"][0]["action"] == "already_synced"
    result = apply_backfill_plan(engine, MODELS, second, config=config, now=NOW + timedelta(minutes=3), code_revision=CODE_REVISION)
    assert result.actions == {"already_synced": 1}

    with Session(engine) as session:
        person = session.scalar(select(Persona))
        assert person.id == original_id
        assert person.aggiornato_il == original_updated_at
        assert tuple(session.scalars(select(RecapitoPersona.id).order_by(RecapitoPersona.id)).all()) == contact_ids


def test_source_change_invalidates_plan(engine, config):
    with Session(engine) as session:
        source = add_source(session)
        source_id = source.id
        session.commit()
    plan = build_plan(engine, config)
    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.telefono = "3339999999"
        source.aggiornato_il = NOW
        session.commit()
    with pytest.raises(StalePlanError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)


def test_expired_plan_is_rejected(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    with pytest.raises(ExpiredPlanError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(hours=2), code_revision=CODE_REVISION)


def test_collisions_warn_but_never_deduplicate(engine, config):
    with Session(engine) as session:
        add_source(session, nome="Persona Uno")
        add_source(session, nome="Persona Due")
        session.commit()
    plan = build_plan(engine, config)
    assert all("DUPLICATE_NORMALIZED_TAX_CODE" in record["warnings"] for record in plan["records"])
    assert all("DUPLICATE_NORMALIZED_PHONE" in record["warnings"] for record in plan["records"])
    assert all("DUPLICATE_NORMALIZED_EMAIL" in record["warnings"] for record in plan["records"])
    assert all(set(group) == {"code", "legacy_ids"} for group in plan["collisions"])
    assert all(group["legacy_ids"] == [1, 2] for group in plan["collisions"])
    apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 2
        assert session.scalar(select(pb.func.count()).select_from(SegnalazioneDuplicato)) == 0
        assert session.scalar(select(pb.func.count()).select_from(FusionePersona)) == 0


def test_invalid_contact_is_omitted_and_existing_is_archived(engine, config):
    with Session(engine) as session:
        source = add_source(session)
        source_id = source.id
        session.commit()
    first = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, first, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)

    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.telefono = "abc1"
        source.aggiornato_il = NOW + timedelta(minutes=2)
        session.commit()
    second = build_plan(engine, config, now=NOW + timedelta(minutes=3))
    assert "INVALID_PHONE" in second["records"][0]["warnings"]
    apply_backfill_plan(engine, MODELS, second, config=config, now=NOW + timedelta(minutes=4), code_revision=CODE_REVISION)

    with Session(engine) as session:
        phone = session.scalar(select(RecapitoPersona).where(RecapitoPersona.tipo == "telefono"))
        assert phone.archiviato_il is not None
        assert phone.principale is False


def test_historical_contact_is_reactivated(engine, config):
    with Session(engine) as session:
        source = add_source(session, telefono="3331111111")
        source_id = source.id
        session.commit()
    p1 = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, p1, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.telefono = "3332222222"
        source.aggiornato_il = NOW + timedelta(minutes=2)
        session.commit()
    p2 = build_plan(engine, config, now=NOW + timedelta(minutes=3))
    apply_backfill_plan(engine, MODELS, p2, config=config, now=NOW + timedelta(minutes=4), code_revision=CODE_REVISION)
    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.telefono = "3331111111"
        source.aggiornato_il = NOW + timedelta(minutes=5)
        session.commit()
    p3 = build_plan(engine, config, now=NOW + timedelta(minutes=6))
    apply_backfill_plan(engine, MODELS, p3, config=config, now=NOW + timedelta(minutes=7), code_revision=CODE_REVISION)
    with Session(engine) as session:
        phones = session.scalars(select(RecapitoPersona).where(RecapitoPersona.tipo == "telefono").order_by(RecapitoPersona.id)).all()
        assert len(phones) == 2
        active = [phone for phone in phones if phone.archiviato_il is None]
        assert len(active) == 1
        assert active[0].valore_normalizzato == "3331111111"


def test_anonymization_deletes_v2_contacts_and_pii(engine, config):
    with Session(engine) as session:
        source = add_source(session)
        source_id = source.id
        session.commit()
    p1 = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, p1, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)

    anonymized_at = NOW + timedelta(minutes=2)
    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.nome = ANONYMIZED_PERSON_PLACEHOLDER
        source.telefono = None
        source.email = None
        source.codice_fiscale = None
        source.nome_bambino = None
        source.eta_bambino = None
        source.note = None
        source.dati_anonimizzati_il = anonymized_at
        source.aggiornato_il = anonymized_at
        session.commit()

    p2 = build_plan(engine, config, now=NOW + timedelta(minutes=3))
    assert p2["records"][0]["action"] == "anonymize"
    apply_backfill_plan(engine, MODELS, p2, config=config, now=NOW + timedelta(minutes=4), code_revision=CODE_REVISION)

    with Session(engine) as session:
        person = session.scalar(select(Persona))
        assert person.stato == "archiviata"
        assert person.archiviato_il == anonymized_at
        assert person.legacy_nome_completo is None
        assert person.codice_fiscale is None
        assert session.scalar(select(pb.func.count()).select_from(RecapitoPersona)) == 0
        audits = session.scalars(select(RegistroEvento)).all()
        serialized = json.dumps([audit.dettagli for audit in audits])
        assert SENTINEL_PHONE not in serialized
        assert SENTINEL_EMAIL not in serialized


def test_anonymization_reversal_is_blocked(engine, config):
    with Session(engine) as session:
        source = add_source(
            session,
            nome=ANONYMIZED_PERSON_PLACEHOLDER,
            telefono=None,
            email=None,
            codice_fiscale=None,
            dati_anonimizzati_il=NOW - timedelta(days=1),
        )
        source_id = source.id
        session.commit()
    first = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, first, config=config, now=NOW, code_revision=CODE_REVISION)

    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.nome = "Ritornata Attiva"
        source.telefono = "3331234567"
        source.email = "ritorno@example.test"
        source.dati_anonimizzati_il = None
        source.aggiornato_il = NOW + timedelta(minutes=1)
        session.commit()
    second = build_plan(engine, config, now=NOW + timedelta(minutes=2))
    assert "ANONYMIZATION_REVERSED" in second["records"][0]["blockers"]
    with pytest.raises(BackfillBlockerError) as captured:
        apply_backfill_plan(engine, MODELS, second, config=config, now=NOW + timedelta(minutes=3), code_revision=CODE_REVISION)
    assert captured.value.failure_result is not None
    assert captured.value.failure_result.report()["status"] == "errore"
    assert captured.value.failure_result.report()["error_code"] == "BACKFILL_BLOCKER"


def test_specific_plan_blockers_are_preserved_in_failure_report_and_audit(engine, config):
    residual_phone = "3339998877"
    with Session(engine) as session:
        for suffix in ("1", "2"):
            add_source(
                session,
                nome=ANONYMIZED_PERSON_PLACEHOLDER,
                telefono=residual_phone + suffix,
                email=None,
                codice_fiscale=None,
                dati_anonimizzati_il=NOW - timedelta(days=1),
            )
        session.commit()

    plan = build_plan(engine, config)
    expected = {"ANONYMIZED_SOURCE_HAS_RESIDUAL_PII": 2}
    assert plan["summary"]["blockers"] == expected

    with pytest.raises(BackfillBlockerError) as captured:
        apply_backfill_plan(
            engine,
            MODELS,
            plan,
            config=config,
            now=NOW + timedelta(minutes=1),
            code_revision=CODE_REVISION,
        )

    report = captured.value.failure_result.report()
    assert report["error_code"] == "BACKFILL_BLOCKER"
    assert report["blockers"] == expected
    assert residual_phone not in json.dumps(report, sort_keys=True)

    with Session(engine) as session:
        event = session.scalar(
            select(RegistroEvento).where(RegistroEvento.esito == "errore")
        )
        audit = json.loads(event.dettagli)
        assert audit["error_code"] == "BACKFILL_BLOCKER"
        assert audit["blocker_codes"] == ["ANONYMIZED_SOURCE_HAS_RESIDUAL_PII"]
        assert residual_phone not in event.dettagli


def test_out_of_phase_target_blocks_apply(engine, config):
    with Session(engine) as session:
        source = add_source(session)
        session.flush()
        session.add(
            Persona(
                legacy_persona_corso_id=source.id,
                nome="Manuale",
                stato="attiva",
                anagrafica_da_verificare=True,
                creato_il=NOW,
                aggiornato_il=NOW,
            )
        )
        session.commit()
    plan = build_plan(engine, config)
    assert "TARGET_OUT_OF_PHASE_CHANGE" in plan["records"][0]["blockers"]


def test_populated_practice_fk_blocks_phase(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.add(Appuntamento(persona_id=99))
        session.commit()
    plan = build_plan(engine, config)
    assert "PRACTICE_V2_FK_ALREADY_POPULATED" in plan["global_blockers"]


def test_rollback_is_total_and_failure_audit_is_separate(engine, config, monkeypatch):
    with Session(engine) as session:
        add_source(session, nome="Uno")
        add_source(session, nome="Due", telefono="3337777777", email="due@example.test", codice_fiscale="RSSMRA80A01H502U")
        session.commit()
    plan = build_plan(engine, config)

    original = pb._apply_source_projection
    calls = {"count": 0}

    def failing(*args, **kwargs):
        calls["count"] += 1
        result = original(*args, **kwargs)
        if calls["count"] == 2:
            raise RuntimeError("synthetic failure")
        return result

    monkeypatch.setattr(pb, "_apply_source_projection", failing)
    with pytest.raises(pb.ApplyExecutionError) as captured:
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    assert captured.value.code == "PATIENT_BACKFILL_ERROR"
    assert captured.value.failure_result is not None
    assert captured.value.failure_result.report()["error_code"] == "PATIENT_BACKFILL_ERROR"
    assert "synthetic failure" not in str(captured.value)

    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 0
        assert session.scalar(select(pb.func.count()).select_from(RecapitoPersona)) == 0
        error_event = session.scalar(select(RegistroEvento).where(RegistroEvento.esito == "errore"))
        assert error_event is not None
        assert SENTINEL_NAME not in (error_event.dettagli or "")


def test_sqlite_second_writer_fails_fast(engine):
    acquired = threading.Event()
    release = threading.Event()
    errors = []

    def first_writer():
        with pb.apply_session(engine):
            acquired.set()
            release.wait(timeout=3)

    thread = threading.Thread(target=first_writer)
    thread.start()
    assert acquired.wait(timeout=2)
    start = time.monotonic()
    try:
        with pytest.raises(ConcurrentBackfillError):
            with pb.apply_session(engine):
                pass
    except Exception as exc:
        errors.append(exc)
    finally:
        release.set()
        thread.join(timeout=3)
    assert not errors
    assert time.monotonic() - start < 1.0


def test_dry_run_result_is_minimized(engine, config):
    with Session(engine) as session:
        add_source(session, note=SENTINEL_NOTE)
        session.commit()
    plan = build_plan(engine, config)
    report = dry_run_result(plan).report()
    serialized = json.dumps(report)
    assert SENTINEL_NAME not in serialized
    assert SENTINEL_NOTE not in serialized
    assert report["mode"] == "dry-run"


def test_noop_plan_can_be_reused_without_target_timestamp_changes(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    first = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, first, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    noop = build_plan(engine, config, now=NOW + timedelta(minutes=2))
    assert noop["records"][0]["action"] == "already_synced"
    apply_backfill_plan(engine, MODELS, noop, config=config, now=NOW + timedelta(minutes=3), code_revision=CODE_REVISION)
    apply_backfill_plan(engine, MODELS, noop, config=config, now=NOW + timedelta(minutes=4), code_revision=CODE_REVISION)
    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 1
        assert session.scalar(select(pb.func.count()).select_from(RecapitoPersona)) == 2


def test_environment_mismatch_is_rejected(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    other = dict(config)
    other["APP_ENV"] = "staging"
    with pytest.raises(pb.EnvironmentMismatchError):
        apply_backfill_plan(engine, MODELS, plan, config=other, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)


def test_code_revision_mismatch_is_rejected(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    with pytest.raises(pb.CodeRevisionError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision="different")


def test_plan_reader_rejects_group_readable_file(tmp_path, engine, config):
    plan = build_plan(engine, config)
    path = tmp_path / "weak.json"
    write_plan_file(path, plan)
    os.chmod(path, 0o640)
    with pytest.raises(InvalidPlanError):
        read_plan_file_secure(path)


def test_unexpected_integrity_error_is_sanitized_everywhere(engine, config, monkeypatch, caplog):
    with Session(engine) as session:
        add_source(session, nome=SENTINEL_NAME, telefono=SENTINEL_PHONE, email=SENTINEL_EMAIL)
        session.commit()
    plan = build_plan(engine, config)

    def failing(*args, **kwargs):
        raise IntegrityError(
            "INSERT INTO persona(nome, telefono) VALUES (:name, :phone)",
            {"name": SENTINEL_NAME, "phone": SENTINEL_PHONE},
            RuntimeError(SENTINEL_EMAIL),
        )

    monkeypatch.setattr(pb, "_apply_source_projection", failing)
    caplog.set_level("ERROR")
    with pytest.raises(pb.ApplyExecutionError) as captured:
        apply_backfill_plan(
            engine,
            MODELS,
            plan,
            config=config,
            now=NOW + timedelta(minutes=1),
            code_revision=CODE_REVISION,
        )

    exc = captured.value
    assert exc.code == "UNEXPECTED_INTEGRITY_ERROR"
    assert str(exc) == "UNEXPECTED_INTEGRITY_ERROR"
    assert exc.__cause__ is None
    assert exc.__context__ is None

    seen = set()
    cursor = exc
    chain_text = []
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        chain_text.extend([type(cursor).__name__, str(cursor), repr(cursor), repr(getattr(cursor, "args", ()))])
        for attr in ("statement", "params"):
            if hasattr(cursor, attr):
                chain_text.append(repr(getattr(cursor, attr)))
        cursor = cursor.__cause__ or cursor.__context__
    chain_serialized = "\n".join(chain_text)
    serialized_report = json.dumps(exc.failure_result.report(), sort_keys=True)
    for sentinel in (SENTINEL_NAME, SENTINEL_PHONE, SENTINEL_EMAIL):
        assert sentinel not in str(exc)
        assert sentinel not in chain_serialized
        assert sentinel not in serialized_report
        assert sentinel not in caplog.text

    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 0
        event_row = session.scalar(select(RegistroEvento).where(RegistroEvento.esito == "errore"))
        assert event_row is not None
        audit_text = f"{event_row.messaggio or ''} {event_row.dettagli or ''}"
        for sentinel in (SENTINEL_NAME, SENTINEL_PHONE, SENTINEL_EMAIL):
            assert sentinel not in audit_text


def test_failure_audit_failure_is_logged_without_secondary_message(engine, config, monkeypatch, caplog):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)

    def failing_projection(*args, **kwargs):
        raise RuntimeError(SENTINEL_NAME)

    def failing_audit(*args, **kwargs):
        raise RuntimeError(SENTINEL_EMAIL)

    monkeypatch.setattr(pb, "_apply_source_projection", failing_projection)
    monkeypatch.setattr(pb, "_failure_audit_event", failing_audit)
    caplog.set_level("ERROR")

    with pytest.raises(pb.ApplyExecutionError) as captured:
        apply_backfill_plan(
            engine,
            MODELS,
            plan,
            config=config,
            now=NOW + timedelta(minutes=1),
            code_revision=CODE_REVISION,
        )
    assert captured.value.code == "PATIENT_BACKFILL_ERROR"
    assert "audit_error_type=RuntimeError" in caplog.text
    assert SENTINEL_NAME not in caplog.text
    assert SENTINEL_EMAIL not in caplog.text


def test_display_only_contact_change_is_planned_as_update(engine, config):
    with Session(engine) as session:
        source = add_source(session, telefono="+39 333 123 4567")
        session.commit()
        source_id = source.id
    first = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, first, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)

    with Session(engine) as session:
        source = session.get(PersonaCorso, source_id)
        source.telefono = "0039 333 123 4567"
        source.aggiornato_il = NOW + timedelta(minutes=2)
        session.commit()
    second = build_plan(engine, config, now=NOW + timedelta(minutes=3))
    assert second["records"][0]["action"] == "update"

    apply_backfill_plan(engine, MODELS, second, config=config, now=NOW + timedelta(minutes=4), code_revision=CODE_REVISION)
    with Session(engine) as session:
        person = session.scalar(select(Persona))
        phone = session.scalar(select(RecapitoPersona).where(RecapitoPersona.tipo == "telefono", RecapitoPersona.archiviato_il.is_(None)))
        assert phone.valore == "0039 333 123 4567"
        assert person.aggiornato_il == NOW + timedelta(minutes=4)


def test_extra_active_nonprincipal_contact_forces_update_and_archive(engine, config):
    with Session(engine) as session:
        add_source(session, telefono="3331234567")
        session.commit()
    first = build_plan(engine, config)
    apply_backfill_plan(engine, MODELS, first, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)

    with Session(engine) as session:
        person = session.scalar(select(Persona))
        session.add(
            RecapitoPersona(
                persona_id=person.id,
                tipo="telefono",
                valore="3339999999",
                valore_normalizzato="3339999999",
                principale=False,
                etichetta=None,
                creato_il=NOW + timedelta(minutes=1),
                archiviato_il=None,
            )
        )
        session.commit()

    plan = build_plan(engine, config, now=NOW + timedelta(minutes=2))
    assert plan["records"][0]["action"] == "update"
    apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=3), code_revision=CODE_REVISION)
    with Session(engine) as session:
        active = list(session.scalars(select(RecapitoPersona).where(RecapitoPersona.tipo == "telefono", RecapitoPersona.archiviato_il.is_(None))).all())
        assert len(active) == 1
        assert active[0].principale is True
        archived = list(session.scalars(select(RecapitoPersona).where(RecapitoPersona.tipo == "telefono", RecapitoPersona.archiviato_il.is_not(None))).all())
        assert len(archived) == 1
        assert archived[0].principale is False


@pytest.mark.parametrize("bad_name", ["x" * 101, 12345])
def test_anomalous_legacy_name_is_warning_not_dry_run_crash(bad_name):
    source = type(
        "S",
        (),
        {
            "id": 1,
            "nome": bad_name,
            "telefono": None,
            "email": None,
            "codice_fiscale": None,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": None,
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert assessment.legacy_name is None
    assert "MISSING_LEGACY_NAME" in assessment.warnings


def test_anonymized_source_with_invalid_name_is_blocked_without_leaking_name():
    bad_name = SENTINEL_NAME + ("x" * 120)
    source = type(
        "S",
        (),
        {
            "id": 1,
            "nome": bad_name,
            "telefono": None,
            "email": None,
            "codice_fiscale": None,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": NOW - timedelta(days=1),
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert "ANONYMIZED_SOURCE_HAS_RESIDUAL_PII" in assessment.blockers
    assert bad_name not in repr(assessment.blockers)


def test_future_anonymization_timestamp_is_blocked():
    source = type(
        "S",
        (),
        {
            "id": 1,
            "nome": ANONYMIZED_PERSON_PLACEHOLDER,
            "telefono": None,
            "email": None,
            "codice_fiscale": None,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": NOW + timedelta(minutes=1),
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert "INVALID_ANONYMIZATION_TIMESTAMP" in assessment.blockers


def test_source_inserted_after_plan_makes_plan_stale(engine, config):
    with Session(engine) as session:
        add_source(session, nome="Uno")
        session.commit()
    plan = build_plan(engine, config)
    with Session(engine) as session:
        add_source(session, nome="Due", telefono="3330000000", email="due@example.test", codice_fiscale="RSSMRA80A01H502U")
        session.commit()
    with pytest.raises(StalePlanError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)


def test_source_removed_after_plan_makes_plan_stale(engine, config):
    with Session(engine) as session:
        source = add_source(session)
        session.commit()
        source_id = source.id
    plan = build_plan(engine, config)
    with Session(engine) as session:
        session.delete(session.get(PersonaCorso, source_id))
        session.commit()
    with pytest.raises(StalePlanError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)


def test_rerun_after_rollback_succeeds_with_new_plan(engine, config, monkeypatch):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    original = pb._apply_source_projection

    def fail_once(*args, **kwargs):
        raise RuntimeError("do-not-expose")

    monkeypatch.setattr(pb, "_apply_source_projection", fail_once)
    with pytest.raises(pb.ApplyExecutionError):
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    monkeypatch.setattr(pb, "_apply_source_projection", original)

    new_plan = build_plan(engine, config, now=NOW + timedelta(minutes=2))
    result = apply_backfill_plan(engine, MODELS, new_plan, config=config, now=NOW + timedelta(minutes=3), code_revision=CODE_REVISION)
    assert result.status == "successo"
    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 1


def test_plan_writer_enforces_same_size_limit_as_reader(tmp_path, engine, config, monkeypatch):
    plan = build_plan(engine, config)
    encoded_size = len(pb.canonical_json_bytes(plan)) + 1
    path = tmp_path / "limit.json"

    monkeypatch.setattr(pb, "MAX_PLAN_FILE_BYTES", encoded_size)
    write_plan_file(path, plan)
    assert read_plan_file_secure(path)["run_id"] == plan["run_id"]

    path.unlink()
    monkeypatch.setattr(pb, "MAX_PLAN_FILE_BYTES", encoded_size - 1)
    with pytest.raises(InvalidPlanError):
        write_plan_file(path, plan)
    assert not path.exists()


def test_result_reports_source_counts(engine, config):
    with Session(engine) as session:
        add_source(session, nome="Attiva")
        add_source(
            session,
            nome=ANONYMIZED_PERSON_PLACEHOLDER,
            telefono=None,
            email=None,
            codice_fiscale=None,
            nome_bambino=None,
            eta_bambino=None,
            note=None,
            dati_anonimizzati_il=NOW - timedelta(days=1),
        )
        session.commit()
    plan = build_plan(engine, config)
    dry_report = dry_run_result(plan).report()
    assert dry_report["source_count"] == 2
    assert dry_report["active_sources"] == 1
    assert dry_report["anonymized_sources"] == 1


def test_paths_equivalent_detects_symlink_alias(tmp_path):
    destination = tmp_path / "plan.json"
    destination.write_text("{}", encoding="utf-8")
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(destination)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink non supportati.")
    assert pb.paths_equivalent(destination, alias) is True
    assert pb.paths_equivalent(destination, destination) is True
    assert pb.paths_equivalent(destination, tmp_path / "other.json") is False


def test_plan_key_rejects_short_secret_with_specific_code(config):
    config = dict(config, SECRET_KEY="short", SECRET_KEY_IS_EPHEMERAL=False)
    with pytest.raises(pb.PatientBackfillError) as captured:
        get_plan_key(config)
    assert captured.value.code == "UNSTABLE_PLAN_KEY"


def test_plan_signed_with_different_key_is_rejected(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    other_config = dict(config, SECRET_KEY="z" * 64)
    with pytest.raises(InvalidPlanError):
        verify_plan_signature(plan, get_plan_key(other_config))


@pytest.mark.parametrize("mutation", ["action", "legacy_id", "expires_at", "warnings"])
def test_plan_signature_rejects_required_signed_mutations(engine, config, mutation):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    if mutation == "action":
        plan["records"][0]["action"] = "already_synced"
    elif mutation == "legacy_id":
        plan["records"][0]["legacy_id"] += 100
    elif mutation == "expires_at":
        plan["expires_at"] = "2026-09-07T13:30:00.000000Z"
    elif mutation == "warnings":
        plan["records"][0]["warnings"] = ["MISSING_LEGACY_NAME"]
    with pytest.raises(InvalidPlanError):
        verify_plan_signature(plan, get_plan_key(config))


def test_unicode_name_and_tax_code_are_projected_without_inference():
    source = type(
        "S",
        (),
        {
            "id": 17,
            "nome": "  Łucía D’Angelo  ",
            "telefono": None,
            "email": None,
            "codice_fiscale": " rssmra80a01h501u ",
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": None,
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert assessment.legacy_name == "Łucía D’Angelo"
    assert assessment.tax_code == "RSSMRA80A01H501U"
    assert "INVALID_TAX_CODE" not in assessment.warnings


def test_invalid_tax_code_and_email_become_warnings_without_pii():
    source = type(
        "S",
        (),
        {
            "id": 18,
            "nome": "Persona Test",
            "telefono": None,
            "email": "not-an-email-PII_SENTINEL",
            "codice_fiscale": "X" * 33,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": None,
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert assessment.tax_code is None
    assert assessment.email_normalized is None
    assert {"INVALID_TAX_CODE", "INVALID_EMAIL"} <= assessment.warnings
    assert "PII_SENTINEL" not in repr(sorted(assessment.warnings))


def test_invalid_anonymization_timestamp_type_is_blocked_without_crash():
    source = type(
        "S",
        (),
        {
            "id": 19,
            "nome": ANONYMIZED_PERSON_PLACEHOLDER,
            "telefono": None,
            "email": None,
            "codice_fiscale": None,
            "nome_bambino": None,
            "eta_bambino": None,
            "note": None,
            "dati_anonimizzati_il": "not-a-datetime",
        },
    )()
    assessment = analyze_legacy_source(source, NOW)
    assert "INVALID_ANONYMIZATION_TIMESTAMP" in assessment.blockers


def test_source_fingerprint_covers_complete_legacy_business_snapshot(config):
    key = get_plan_key(config)
    base = {
        "id": 1,
        "nome": "Persona",
        "telefono": "3331234567",
        "email": "persona@example.test",
        "codice_fiscale": "RSSMRA80A01H501U",
        "nome_bambino": "Bimbo",
        "eta_bambino": "12 mesi",
        "note": "nota",
        "creato_il": NOW - timedelta(days=3),
        "aggiornato_il": NOW - timedelta(days=1),
        "dati_anonimizzati_il": None,
    }
    original = type("S", (), base)()
    original_fp = pb.source_fingerprint(original, key)
    for field, replacement in {
        "nome": "Altro",
        "telefono": "3339999999",
        "email": "altro@example.test",
        "codice_fiscale": "ALTRO",
        "nome_bambino": "Altro Bimbo",
        "eta_bambino": "13 mesi",
        "note": "altra nota",
        "creato_il": NOW - timedelta(days=4),
        "aggiornato_il": NOW,
        "dati_anonimizzati_il": NOW - timedelta(hours=1),
    }.items():
        changed = dict(base)
        changed[field] = replacement
        assert pb.source_fingerprint(type("S", (), changed)(), key) != original_fp, field


def test_specific_preflight_error_codes_and_phases(engine, config, monkeypatch):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)

    short_config = dict(config, SECRET_KEY="short", SECRET_KEY_IS_EPHEMERAL=False)
    with pytest.raises(pb.PatientBackfillError) as unstable:
        apply_backfill_plan(engine, MODELS, plan, config=short_config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    assert unstable.value.code == "UNSTABLE_PLAN_KEY"
    assert unstable.value.failure_result.error_code == "UNSTABLE_PLAN_KEY"
    assert unstable.value.failure_result.error_phase == "preflight"

    def unknown_revision(*args, **kwargs):
        raise pb.PatientBackfillError(code="CODE_REVISION_UNKNOWN")

    monkeypatch.setattr(pb, "resolve_code_revision", unknown_revision)
    with pytest.raises(pb.PatientBackfillError) as unknown:
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1))
    assert unknown.value.code == "CODE_REVISION_UNKNOWN"
    assert unknown.value.failure_result.error_code == "CODE_REVISION_UNKNOWN"
    assert unknown.value.failure_result.error_phase == "preflight"


def test_a1_not_ready_code_is_preserved_in_report_and_audit(engine, config):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='wrong'"))
    with pytest.raises(pb.PatientBackfillError) as captured:
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW + timedelta(minutes=1), code_revision=CODE_REVISION)
    exc = captured.value
    assert exc.code == "A1_NOT_READY"
    report = exc.failure_result.report()
    assert report["error_code"] == "A1_NOT_READY"
    assert report["error_phase"] == "revalidation"
    assert report["blockers"] == {"A1_NOT_READY": 1}
    with Session(engine) as session:
        row = session.scalar(select(RegistroEvento).where(RegistroEvento.esito == "errore"))
        payload = json.loads(row.dettagli)
        assert payload["error_code"] == "A1_NOT_READY"
        assert payload["error_phase"] == "revalidation"


def test_testing_config_ignores_generic_database_url_in_subprocess(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql+psycopg://danger:danger@127.0.0.1:1/real_like_db"
    env.pop("PAZ_A2_TEST_DATABASE_URL", None)
    script = (
        "from config import TestingConfig; "
        "print(TestingConfig.SQLALCHEMY_DATABASE_URI); "
        "print(TestingConfig.DATABASE_URL_IS_EXPLICIT)"
    )
    import subprocess, sys
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.stdout.splitlines() == ["sqlite:///:memory:", "False"]


def test_failure_report_marks_lock_phase(engine, config, monkeypatch):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)

    from contextlib import contextmanager

    @contextmanager
    def fail_lock(_engine):
        raise ConcurrentBackfillError()
        yield  # pragma: no cover

    monkeypatch.setattr(pb, "apply_session", fail_lock)
    with pytest.raises(ConcurrentBackfillError) as caught:
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW, code_revision=CODE_REVISION)
    assert caught.value.failure_result.error_code == "CONCURRENT_A2_APPLY"
    assert caught.value.failure_result.error_phase == "lock"


def test_failure_report_marks_audit_phase_and_rolls_back(engine, config, monkeypatch):
    with Session(engine) as session:
        add_source(session)
        session.commit()
    plan = build_plan(engine, config)

    def fail_success_audit(*args, **kwargs):
        raise pb.PatientBackfillError(code="PATIENT_BACKFILL_ERROR")

    monkeypatch.setattr(pb, "_success_audit_event", fail_success_audit)
    with pytest.raises(pb.PatientBackfillError) as caught:
        apply_backfill_plan(engine, MODELS, plan, config=config, now=NOW, code_revision=CODE_REVISION)
    assert caught.value.failure_result.error_code == "PATIENT_BACKFILL_ERROR"
    assert caught.value.failure_result.error_phase == "audit"
    with Session(engine) as session:
        assert session.scalar(select(pb.func.count()).select_from(Persona)) == 0
        events = session.scalars(select(RegistroEvento).where(RegistroEvento.esito == "errore")).all()
        assert events
        payload = json.loads(events[-1].dettagli)
        assert payload["error_phase"] == "audit"


def test_paths_equivalent_handles_symlink_loop_without_traceback(tmp_path):
    first = tmp_path / "loop-a.json"
    second = tmp_path / "loop-b.json"
    first.symlink_to(second.name)
    second.symlink_to(first.name)
    # The helper must not leak RuntimeError from Path.resolve().
    assert pb.paths_equivalent(first, second) is False
