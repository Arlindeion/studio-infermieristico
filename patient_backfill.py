"""PAZ-A2 identity backfill for Patients 2.0.

This module deliberately stays independent from Flask.  The web application
passes its SQLAlchemy models, engine and configuration explicitly.  PAZ-A2 is
an operational backfill, not an Alembic data migration: dry-run builds a signed
plan; apply revalidates source and target under one database transaction and
lock before writing anything.

The module must never log or serialize patient-identifying values.  Names,
contacts, tax codes and legacy notes are used only in memory to derive target
values and keyed fingerprints.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Iterable, Mapping, Sequence
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from patient_backfill_artifacts import (
    ArtifactSecurityError,
    MAX_ARTIFACT_FILE_BYTES,
    atomic_write_private_json,
    canonical_json_bytes,
    delete_private_file,
    paths_equivalent,
    read_private_json,
)
from patient_backfill_db import (
    ConcurrentApplyLockError,
    UnsupportedBackfillDialectError,
    apply_session as database_apply_session,
)
from patient_backfill_plan import (
    ACTION_CODES,
    BLOCKER_CODES,
    DEFAULT_PLAN_TTL_SECONDS,
    ERROR_CODES,
    PLAN_PURPOSE,
    PLAN_VERSION,
    WARNING_CODES,
    CodeRevisionError,
    ConcurrentBackfillError,
    EnvironmentMismatchError,
    ExpiredPlanError,
    InvalidPlanError,
    PatientBackfillError,
    StalePlanError,
    StaleTargetError,
    _datetime_to_utc_iso,
    _hmac_hex,
    _parse_utc_iso,
    database_environment_fingerprint,
    get_plan_key,
    read_alembic_revision,
    resolve_code_revision,
    sanitize_blocker_codes,
    sanitize_error_code,
    sign_plan,
    utc_now_naive,
    validate_plan_schema,
    verify_plan_signature,
)
MAX_PLAN_FILE_BYTES = MAX_ARTIFACT_FILE_BYTES
LOGGER = logging.getLogger(__name__)

POSTGRES_ADVISORY_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"SC-Studio-PAZ-A2-identity-backfill").digest()[:8],
    byteorder="big",
    signed=True,
)

from patient_data import (
    ANONYMIZED_PERSON_PLACEHOLDER,
    PatientDataValidationError,
    normalize_email_address,
    normalize_patient_name,
    normalize_phone_number,
    normalize_tax_code,
)


class BackfillBlockerError(PatientBackfillError):
    code = "BACKFILL_BLOCKER"

    def __init__(self, blocker_codes: Sequence[str]):
        self.blocker_codes = sanitize_blocker_codes(blocker_codes) or ("BACKFILL_BLOCKER",)
        super().__init__("Backfill bloccato: " + ", ".join(self.blocker_codes))


class ApplyExecutionError(PatientBackfillError):
    """Sanitized apply failure exposed across the service/CLI boundary."""

    def __init__(self, code: str, result: "ApplyResult"):
        self.code = sanitize_error_code(code)
        self.result = result
        self.failure_result = result
        # Never include the original DB exception message or chaining here.
        Exception.__init__(self, self.code)


@dataclass(frozen=True)
class BackfillModels:
    PersonaCorso: Any
    Persona: Any
    RecapitoPersona: Any
    RelazionePersona: Any
    SegnalazioneDuplicato: Any
    FusionePersona: Any
    Appuntamento: Any
    CallSonno: Any
    IscrizioneCorso: Any
    RegistroEvento: Any


@dataclass
class SourceAssessment:
    legacy_id: int
    active: bool
    anonymized: bool
    legacy_name: str | None
    tax_code: str | None
    phone_display: str | None
    phone_normalized: str | None
    email_display: str | None
    email_normalized: str | None
    warnings: set[str] = field(default_factory=set)
    blockers: set[str] = field(default_factory=set)


@dataclass
class ApplyResult:
    run_id: str
    mode: str
    status: str
    actions: dict[str, int]
    contacts: dict[str, int]
    warning_counts: dict[str, int]
    blocker_counts: dict[str, int]
    source_count: int = 0
    active_sources: int = 0
    anonymized_sources: int = 0
    collisions: list[dict[str, Any]] = field(default_factory=list)
    plan_digest: str | None = None
    error_code: str | None = None
    error_phase: str | None = None

    def report(self) -> dict[str, Any]:
        report = {
            "run_id": self.run_id,
            "mode": self.mode,
            "status": self.status,
            "source_count": self.source_count,
            "active_sources": self.active_sources,
            "anonymized_sources": self.anonymized_sources,
            "actions": dict(sorted(self.actions.items())),
            "contacts": dict(sorted(self.contacts.items())),
            "warnings": dict(sorted(self.warning_counts.items())),
            "blockers": dict(sorted(self.blocker_counts.items())),
            "collisions": self.collisions,
            "plan_digest": self.plan_digest,
        }
        if self.error_code is not None:
            report["error_code"] = self.error_code
        if self.error_phase is not None:
            report["error_phase"] = self.error_phase
        return report


# ---------------------------------------------------------------------------
# Source/target projections and privacy analysis
# ---------------------------------------------------------------------------


def _not_blank(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _safe_normalize_name(value: Any) -> tuple[str | None, bool]:
    try:
        normalized = normalize_patient_name(value)
    except (PatientDataValidationError, TypeError):
        return None, True
    return normalized, normalized is None


def _safe_normalize_tax_code(value: Any) -> tuple[str | None, bool]:
    try:
        return normalize_tax_code(value), False
    except (PatientDataValidationError, TypeError):
        return None, True


def _safe_normalize_phone(value: Any) -> tuple[str | None, str | None, bool]:
    display = None if value is None else str(value).strip()
    try:
        normalized = normalize_phone_number(value)
    except (PatientDataValidationError, TypeError):
        return display if display else None, None, True
    return display if display else None, normalized, False


def _safe_normalize_email(value: Any) -> tuple[str | None, str | None, bool]:
    display = None if value is None else str(value).strip()
    try:
        normalized = normalize_email_address(value)
    except (PatientDataValidationError, TypeError):
        return display if display else None, None, True
    return display if display else None, normalized, False


def analyze_legacy_source(source: Any, now: datetime) -> SourceAssessment:
    warnings: set[str] = set()
    blockers: set[str] = set()
    anonymized_at = getattr(source, "dati_anonimizzati_il", None)
    source_name = getattr(source, "nome", None)

    safe_source_name, source_name_invalid = _safe_normalize_name(source_name)
    name_is_placeholder = safe_source_name == ANONYMIZED_PERSON_PLACEHOLDER

    if anonymized_at is None and name_is_placeholder:
        blockers.add("ANONYMIZATION_STATE_INCONSISTENT")

    if anonymized_at is not None:
        if not isinstance(anonymized_at, datetime) or anonymized_at > now:
            blockers.add("INVALID_ANONYMIZATION_TIMESTAMP")
        residual_fields = (
            getattr(source, "telefono", None),
            getattr(source, "email", None),
            getattr(source, "codice_fiscale", None),
            getattr(source, "nome_bambino", None),
            getattr(source, "eta_bambino", None),
            getattr(source, "note", None),
        )
        if source_name_invalid or not name_is_placeholder or any(_not_blank(value) for value in residual_fields):
            blockers.add("ANONYMIZED_SOURCE_HAS_RESIDUAL_PII")
        return SourceAssessment(
            legacy_id=int(source.id),
            active=False,
            anonymized=True,
            legacy_name=None,
            tax_code=None,
            phone_display=None,
            phone_normalized=None,
            email_display=None,
            email_normalized=None,
            warnings=warnings,
            blockers=blockers,
        )

    legacy_name, missing_name = safe_source_name, source_name_invalid or safe_source_name is None
    if missing_name:
        warnings.add("MISSING_LEGACY_NAME")

    tax_code, invalid_tax = _safe_normalize_tax_code(getattr(source, "codice_fiscale", None))
    if invalid_tax:
        warnings.add("INVALID_TAX_CODE")

    phone_display, phone_normalized, invalid_phone = _safe_normalize_phone(getattr(source, "telefono", None))
    if invalid_phone:
        warnings.add("INVALID_PHONE")

    email_display, email_normalized, invalid_email = _safe_normalize_email(getattr(source, "email", None))
    if invalid_email:
        warnings.add("INVALID_EMAIL")

    if _not_blank(getattr(source, "nome_bambino", None)) or _not_blank(getattr(source, "eta_bambino", None)):
        warnings.add("LEGACY_CHILD_FIELDS_PRESENT")
    if _not_blank(getattr(source, "note", None)):
        warnings.add("LEGACY_NOTE_PRESENT")

    return SourceAssessment(
        legacy_id=int(source.id),
        active=True,
        anonymized=False,
        legacy_name=legacy_name,
        tax_code=tax_code,
        phone_display=phone_display if phone_normalized else None,
        phone_normalized=phone_normalized,
        email_display=email_display if email_normalized else None,
        email_normalized=email_normalized,
        warnings=warnings,
        blockers=blockers,
    )


def _source_fingerprint_payload(source: Any) -> dict[str, Any]:
    return {
        "id": int(source.id),
        "nome": getattr(source, "nome", None),
        "telefono": getattr(source, "telefono", None),
        "email": getattr(source, "email", None),
        "codice_fiscale": getattr(source, "codice_fiscale", None),
        "nome_bambino": getattr(source, "nome_bambino", None),
        "eta_bambino": getattr(source, "eta_bambino", None),
        "note": getattr(source, "note", None),
        "creato_il": _datetime_to_utc_iso(getattr(source, "creato_il", None)),
        "aggiornato_il": _datetime_to_utc_iso(getattr(source, "aggiornato_il", None)),
        "dati_anonimizzati_il": _datetime_to_utc_iso(getattr(source, "dati_anonimizzati_il", None)),
    }


def source_fingerprint(source: Any, key: bytes) -> str:
    return _hmac_hex(key, _source_fingerprint_payload(source))


def _contact_fingerprint_payload(contact: Any) -> dict[str, Any]:
    return {
        "id": int(contact.id),
        "tipo": contact.tipo,
        "valore": contact.valore,
        "valore_normalizzato": contact.valore_normalizzato,
        "principale": bool(contact.principale),
        "etichetta": contact.etichetta,
        "creato_il": _datetime_to_utc_iso(contact.creato_il),
        "archiviato_il": _datetime_to_utc_iso(contact.archiviato_il),
    }


def _target_fingerprint_payload(person: Any | None, contacts: Sequence[Any], legacy_id: int) -> dict[str, Any]:
    if person is None:
        return {"exists": False, "legacy_id": legacy_id}
    return {
        "exists": True,
        "legacy_id": legacy_id,
        "id": int(person.id),
        "legacy_persona_corso_id": person.legacy_persona_corso_id,
        "legacy_nome_completo": person.legacy_nome_completo,
        "codice_fiscale": person.codice_fiscale,
        "stato": person.stato,
        "archiviato_il": _datetime_to_utc_iso(person.archiviato_il),
        "anagrafica_da_verificare": bool(person.anagrafica_da_verificare),
        "creato_il": _datetime_to_utc_iso(person.creato_il),
        "aggiornato_il": _datetime_to_utc_iso(person.aggiornato_il),
        "out_of_phase": {
            "nome": person.nome,
            "cognome": person.cognome,
            "data_nascita": str(person.data_nascita) if person.data_nascita is not None else None,
            "sesso_anagrafico": person.sesso_anagrafico,
            "comune_nascita": person.comune_nascita,
            "provincia_nascita": person.provincia_nascita,
            "stato_nascita": person.stato_nascita,
            "indirizzo_residenza": person.indirizzo_residenza,
            "cap_residenza": person.cap_residenza,
            "comune_residenza": person.comune_residenza,
            "provincia_residenza": person.provincia_residenza,
            "stato_residenza": person.stato_residenza,
        },
        "contacts": [_contact_fingerprint_payload(contact) for contact in sorted(contacts, key=lambda item: item.id)],
    }


def target_fingerprint(person: Any | None, contacts: Sequence[Any], legacy_id: int, key: bytes) -> str:
    return _hmac_hex(key, _target_fingerprint_payload(person, contacts, legacy_id))


def _target_has_out_of_phase_data(person: Any | None, contacts: Sequence[Any]) -> bool:
    if person is None:
        return False
    fields = (
        "nome",
        "cognome",
        "data_nascita",
        "sesso_anagrafico",
        "comune_nascita",
        "provincia_nascita",
        "stato_nascita",
        "indirizzo_residenza",
        "cap_residenza",
        "comune_residenza",
        "provincia_residenza",
        "stato_residenza",
    )
    if any(getattr(person, field_name) is not None for field_name in fields):
        return True
    if any(contact.etichetta is not None for contact in contacts):
        return True
    return False


def _expected_person_values(source: Any, assessment: SourceAssessment, apply_now: datetime) -> dict[str, Any]:
    if assessment.anonymized:
        return {
            "legacy_nome_completo": None,
            "codice_fiscale": None,
            "stato": "archiviata",
            "archiviato_il": source.dati_anonimizzati_il,
            "anagrafica_da_verificare": False,
        }
    return {
        "legacy_nome_completo": assessment.legacy_name,
        "codice_fiscale": assessment.tax_code,
        "stato": "attiva",
        "archiviato_il": None,
        "anagrafica_da_verificare": True,
    }


def _contact_state_matches(contacts: Sequence[Any], assessment: SourceAssessment) -> bool:
    if assessment.anonymized:
        return len(contacts) == 0

    expected = {
        "telefono": (assessment.phone_display, assessment.phone_normalized),
        "email": (assessment.email_display, assessment.email_normalized),
    }
    for contact_type, (expected_display, expected_normalized) in expected.items():
        type_contacts = [contact for contact in contacts if contact.tipo == contact_type]
        active = [contact for contact in type_contacts if contact.archiviato_il is None]

        if expected_normalized is None:
            if active:
                return False
        else:
            if len(active) != 1:
                return False
            current = active[0]
            if (
                current.valore_normalizzato != expected_normalized
                or current.valore != expected_display
                or not bool(current.principale)
                or current.etichetta is not None
            ):
                return False

        # Archived contacts may remain as history, but none may retain the
        # principal flag and no extra active/non-principal contact is allowed.
        if any(contact.archiviato_il is not None and bool(contact.principale) for contact in type_contacts):
            return False
    return True


def _determine_action(source: Any, assessment: SourceAssessment, person: Any | None, contacts: Sequence[Any]) -> str:
    if person is None:
        return "create"
    if assessment.active and person.stato == "archiviata":
        return "update"
    if assessment.anonymized and person.stato != "archiviata":
        return "anonymize"
    expected = _expected_person_values(source, assessment, utc_now_naive())
    matches_person = all(getattr(person, key) == value for key, value in expected.items())
    if matches_person and _contact_state_matches(contacts, assessment):
        return "already_synced"
    return "anonymize" if assessment.anonymized else "update"


# ---------------------------------------------------------------------------
# DB inspection and dry-run planning
# ---------------------------------------------------------------------------


def _load_sources(session: Session, models: BackfillModels) -> list[Any]:
    return list(session.scalars(select(models.PersonaCorso).order_by(models.PersonaCorso.id)).all())


def _load_people_by_legacy(session: Session, models: BackfillModels) -> dict[int, Any]:
    rows = session.scalars(
        select(models.Persona)
        .where(models.Persona.legacy_persona_corso_id.is_not(None))
        .order_by(models.Persona.legacy_persona_corso_id)
    ).all()
    return {int(row.legacy_persona_corso_id): row for row in rows}


def _load_contacts_by_person(session: Session, models: BackfillModels, people: Iterable[Any]) -> dict[int, list[Any]]:
    person_ids = [int(person.id) for person in people if person.id is not None]
    if not person_ids:
        return {}
    rows = session.scalars(
        select(models.RecapitoPersona)
        .where(models.RecapitoPersona.persona_id.in_(person_ids))
        .order_by(models.RecapitoPersona.persona_id, models.RecapitoPersona.id)
    ).all()
    result: dict[int, list[Any]] = {}
    for row in rows:
        result.setdefault(int(row.persona_id), []).append(row)
    return result


def _count_non_null(session: Session, column: Any) -> int:
    return int(session.scalar(select(func.count()).where(column.is_not(None))) or 0)


def _global_phase_blockers(session: Session, models: BackfillModels) -> set[str]:
    blockers: set[str] = set()
    practice_count = (
        _count_non_null(session, models.Appuntamento.persona_id)
        + _count_non_null(session, models.CallSonno.persona_id)
        + _count_non_null(session, models.IscrizioneCorso.persona_v2_id)
    )
    if practice_count:
        blockers.add("PRACTICE_V2_FK_ALREADY_POPULATED")

    unexpected_counts = [
        int(session.scalar(select(func.count()).select_from(models.RelazionePersona)) or 0),
        int(session.scalar(select(func.count()).select_from(models.SegnalazioneDuplicato)) or 0),
        int(session.scalar(select(func.count()).select_from(models.FusionePersona)) or 0),
        int(
            session.scalar(
                select(func.count())
                .select_from(models.Persona)
                .where(models.Persona.legacy_persona_corso_id.is_(None))
            )
            or 0
        ),
    ]
    if any(unexpected_counts):
        blockers.add("UNEXPECTED_V2_DOMAIN_DATA")
    return blockers


def _collision_warning_map(assessments: Sequence[SourceAssessment]) -> tuple[dict[int, set[str]], list[dict[str, Any]]]:
    buckets: dict[str, dict[str, list[int]]] = {
        "tax": {},
        "phone": {},
        "email": {},
    }
    for assessment in assessments:
        if not assessment.active:
            continue
        values = {
            "tax": assessment.tax_code,
            "phone": assessment.phone_normalized,
            "email": assessment.email_normalized,
        }
        for kind, value in values.items():
            if value:
                buckets[kind].setdefault(value, []).append(assessment.legacy_id)

    warning_codes = {
        "tax": "DUPLICATE_NORMALIZED_TAX_CODE",
        "phone": "DUPLICATE_NORMALIZED_PHONE",
        "email": "DUPLICATE_NORMALIZED_EMAIL",
    }
    result: dict[int, set[str]] = {}
    collisions: list[dict[str, Any]] = []
    for kind, groups in buckets.items():
        for ids in groups.values():
            if len(ids) < 2:
                continue
            ordered_ids = sorted(ids)
            code = warning_codes[kind]
            collisions.append({"code": code, "legacy_ids": ordered_ids})
            for legacy_id in ordered_ids:
                result.setdefault(legacy_id, set()).add(code)
    collisions.sort(key=lambda item: (item["code"], item["legacy_ids"]))
    return result, collisions


def _build_summary(records: Sequence[dict[str, Any]], assessments: Sequence[SourceAssessment], global_blockers: Sequence[str]) -> dict[str, Any]:
    actions = {code: 0 for code in sorted(ACTION_CODES)}
    warnings = {code: 0 for code in sorted(WARNING_CODES)}
    blockers = {code: 0 for code in sorted(BLOCKER_CODES)}
    contacts = {
        "phone_expected": 0,
        "email_expected": 0,
        "phone_invalid": 0,
        "email_invalid": 0,
    }

    for record in records:
        actions[record["action"]] += 1
        for code in record["warnings"]:
            warnings[code] += 1
        for code in record["blockers"]:
            blockers[code] += 1
    for code in global_blockers:
        blockers[code] += 1

    for assessment in assessments:
        if assessment.phone_normalized:
            contacts["phone_expected"] += 1
        if assessment.email_normalized:
            contacts["email_expected"] += 1
        if "INVALID_PHONE" in assessment.warnings:
            contacts["phone_invalid"] += 1
        if "INVALID_EMAIL" in assessment.warnings:
            contacts["email_invalid"] += 1

    return {
        "actions": {k: v for k, v in actions.items() if v},
        "warnings": {k: v for k, v in warnings.items() if v},
        "blockers": {k: v for k, v in blockers.items() if v},
        "contacts": contacts,
        "active_sources": sum(1 for item in assessments if item.active),
        "anonymized_sources": sum(1 for item in assessments if item.anonymized),
    }


def analyze_backfill_state(session: Session, models: BackfillModels, *, key: bytes, now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], list[dict[str, Any]]]:
    sources = _load_sources(session, models)
    people_by_legacy = _load_people_by_legacy(session, models)
    contacts_by_person = _load_contacts_by_person(session, models, people_by_legacy.values())

    assessments = [analyze_legacy_source(source, now) for source in sources]
    collision_warnings, collisions = _collision_warning_map(assessments)
    global_blockers = sorted(_global_phase_blockers(session, models))

    records: list[dict[str, Any]] = []
    for source, assessment in zip(sources, assessments, strict=True):
        assessment.warnings.update(collision_warnings.get(assessment.legacy_id, set()))
        person = people_by_legacy.get(assessment.legacy_id)
        contacts = contacts_by_person.get(int(person.id), []) if person is not None else []

        blockers = set(assessment.blockers)
        if _target_has_out_of_phase_data(person, contacts):
            blockers.add("TARGET_OUT_OF_PHASE_CHANGE")
        if assessment.active and person is not None and person.stato == "archiviata":
            blockers.add("ANONYMIZATION_REVERSED")

        records.append(
            {
                "legacy_id": assessment.legacy_id,
                "source_updated_at": _datetime_to_utc_iso(getattr(source, "aggiornato_il", None)),
                "source_anonymized_at": _datetime_to_utc_iso(getattr(source, "dati_anonimizzati_il", None)),
                "action": _determine_action(source, assessment, person, contacts),
                "warnings": sorted(assessment.warnings),
                "blockers": sorted(blockers),
                "source_fingerprint": source_fingerprint(source, key),
                "target_fingerprint": target_fingerprint(person, contacts, assessment.legacy_id, key),
            }
        )

    summary = _build_summary(records, assessments, global_blockers)
    return records, summary, global_blockers, collisions


def build_backfill_plan(
    session: Session,
    models: BackfillModels,
    *,
    engine: Engine,
    config: Mapping[str, Any],
    now: datetime | None = None,
    code_revision: str | None = None,
    key: bytes | None = None,
) -> dict[str, Any]:
    generated_at = now or utc_now_naive()
    plan_key = key or get_plan_key(config)
    revision = code_revision or resolve_code_revision(config)
    ttl = config.get("PAZ_A2_PLAN_TTL_SECONDS", DEFAULT_PLAN_TTL_SECONDS)
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0 or ttl > 24 * 3600:
        raise PatientBackfillError("INVALID_PLAN")

    alembic_revision = read_alembic_revision(session)
    records, summary, global_blockers, collisions = analyze_backfill_state(
        session,
        models,
        key=plan_key,
        now=generated_at,
    )
    unsigned = {
        "plan_version": PLAN_VERSION,
        "purpose": PLAN_PURPOSE,
        "run_id": str(uuid.uuid4()),
        "generated_at": _datetime_to_utc_iso(generated_at),
        "expires_at": _datetime_to_utc_iso(generated_at + timedelta(seconds=ttl)),
        "code_revision": revision,
        "alembic_revision": alembic_revision,
        "environment_fingerprint": database_environment_fingerprint(
            engine,
            str(config.get("APP_ENV") or "development"),
            plan_key,
            connection=session.connection(),
        ),
        "source_count": len(records),
        "global_blockers": global_blockers,
        "collisions": collisions,
        "records": records,
        "summary": summary,
    }
    plan = dict(unsigned)
    plan["plan_signature"] = sign_plan(unsigned, plan_key)
    validate_plan_schema(plan)
    return plan


# ---------------------------------------------------------------------------
# Secure artifact I/O wrappers
# ---------------------------------------------------------------------------


def write_plan_file(path: str | os.PathLike, plan: Mapping[str, Any], *, overwrite: bool = False) -> None:
    validate_plan_schema(dict(plan))
    try:
        atomic_write_private_json(path, plan, overwrite=overwrite, max_bytes=MAX_PLAN_FILE_BYTES)
    except ArtifactSecurityError as exc:
        raise InvalidPlanError() from None


def write_report_file(path: str | os.PathLike, report: Mapping[str, Any], *, overwrite: bool = False) -> None:
    try:
        atomic_write_private_json(path, report, overwrite=overwrite, max_bytes=MAX_PLAN_FILE_BYTES)
    except ArtifactSecurityError:
        raise PatientBackfillError("INVALID_PLAN") from None


def read_plan_file_secure(path: str | os.PathLike) -> dict[str, Any]:
    try:
        plan = read_private_json(path, max_bytes=MAX_PLAN_FILE_BYTES)
    except ArtifactSecurityError:
        raise InvalidPlanError() from None
    return validate_plan_schema(plan)


def delete_plan_file(path: str | os.PathLike) -> None:
    try:
        delete_private_file(path)
    except ArtifactSecurityError:
        raise InvalidPlanError() from None


@contextmanager
def apply_session(engine: Engine):
    try:
        with database_apply_session(engine, POSTGRES_ADVISORY_LOCK_KEY) as session:
            yield session
    except ConcurrentApplyLockError:
        raise ConcurrentBackfillError() from None
    except UnsupportedBackfillDialectError:
        raise PatientBackfillError("A1_NOT_READY") from None


def _reconcile_contact(
    session: Session,
    models: BackfillModels,
    person: Any,
    *,
    contact_type: str,
    display_value: str | None,
    normalized_value: str | None,
    now: datetime,
    stats: dict[str, int],
) -> None:
    contacts = list(
        session.scalars(
            select(models.RecapitoPersona)
            .where(
                models.RecapitoPersona.persona_id == person.id,
                models.RecapitoPersona.tipo == contact_type,
            )
            .order_by(models.RecapitoPersona.id)
        ).all()
    )
    matching = next(
        (contact for contact in contacts if normalized_value and contact.valore_normalizzato == normalized_value),
        None,
    )

    for contact in contacts:
        if contact is matching:
            continue
        if contact.archiviato_il is None or contact.principale:
            contact.principale = False
            contact.archiviato_il = now
            stats["archived"] += 1

    if normalized_value is None:
        return

    if matching is None:
        matching = models.RecapitoPersona(
            persona_id=person.id,
            tipo=contact_type,
            valore=display_value,
            valore_normalizzato=normalized_value,
            principale=True,
            etichetta=None,
            creato_il=now,
            archiviato_il=None,
        )
        session.add(matching)
        stats["created"] += 1
        return

    was_archived = matching.archiviato_il is not None
    matching.valore = display_value
    matching.valore_normalizzato = normalized_value
    matching.principale = True
    matching.archiviato_il = None
    if was_archived:
        stats["reactivated"] += 1


def _delete_contacts_for_privacy(session: Session, models: BackfillModels, person_id: int) -> int:
    result = session.execute(
        delete(models.RecapitoPersona).where(models.RecapitoPersona.persona_id == person_id)
    )
    return int(result.rowcount or 0)


def _apply_source_projection(
    session: Session,
    models: BackfillModels,
    source: Any,
    assessment: SourceAssessment,
    person: Any | None,
    *,
    now: datetime,
    contact_stats: dict[str, int],
) -> tuple[Any, str]:
    action = _determine_action(source, assessment, person, [] if person is None else list(person.recapiti))
    if action == "already_synced" and person is not None:
        # A true no-op must not assign ORM attributes, reconcile contacts or
        # update timestamps. The planner owns the exact-state comparison.
        return person, action

    if person is None:
        person = models.Persona(
            legacy_persona_corso_id=source.id,
            nome=None,
            cognome=None,
            data_nascita=None,
            sesso_anagrafico=None,
            comune_nascita=None,
            provincia_nascita=None,
            stato_nascita=None,
            indirizzo_residenza=None,
            cap_residenza=None,
            comune_residenza=None,
            provincia_residenza=None,
            stato_residenza=None,
            creato_il=getattr(source, "creato_il", None) or now,
            aggiornato_il=now,
        )
        session.add(person)
        session.flush()
        action = "create"

    if assessment.anonymized:
        person.legacy_nome_completo = None
        person.codice_fiscale = None
        person.stato = "archiviata"
        person.archiviato_il = source.dati_anonimizzati_il
        person.anagrafica_da_verificare = False
        person.aggiornato_il = now if action != "already_synced" else person.aggiornato_il
        deleted_count = _delete_contacts_for_privacy(session, models, int(person.id))
        contact_stats["privacy_deleted"] += deleted_count
        return person, action

    person.legacy_nome_completo = assessment.legacy_name
    person.codice_fiscale = assessment.tax_code
    person.stato = "attiva"
    person.archiviato_il = None
    person.anagrafica_da_verificare = True

    _reconcile_contact(
        session,
        models,
        person,
        contact_type="telefono",
        display_value=assessment.phone_display,
        normalized_value=assessment.phone_normalized,
        now=now,
        stats=contact_stats,
    )
    _reconcile_contact(
        session,
        models,
        person,
        contact_type="email",
        display_value=assessment.email_display,
        normalized_value=assessment.email_normalized,
        now=now,
        stats=contact_stats,
    )
    if action != "already_synced":
        person.aggiornato_il = now
    return person, action


def _plan_digest(plan: Mapping[str, Any]) -> str:
    return hashlib.sha256(str(plan["plan_signature"]).encode("ascii")).hexdigest()


def _safe_plan_run_id(plan: Any) -> str:
    if not isinstance(plan, Mapping):
        return "unknown"
    value = plan.get("run_id")
    if not isinstance(value, str):
        return "unknown"
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return "unknown"
    return str(parsed) if str(parsed) == value else "unknown"


def _safe_plain_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _safe_count_map(value: Any, allowed: frozenset[str]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, count in value.items():
        if key in allowed and isinstance(key, str):
            parsed = _safe_plain_nonnegative_int(count)
            if parsed:
                result[key] = parsed
    return result


def _plan_source_counts(plan: Any) -> tuple[int, int, int]:
    if not isinstance(plan, Mapping):
        return (0, 0, 0)
    summary = plan.get("summary") if isinstance(plan.get("summary"), Mapping) else {}
    return (
        _safe_plain_nonnegative_int(plan.get("source_count")),
        _safe_plain_nonnegative_int(summary.get("active_sources")),
        _safe_plain_nonnegative_int(summary.get("anonymized_sources")),
    )


def _safe_plan_digest(plan: Any) -> str | None:
    if not isinstance(plan, Mapping):
        return None
    signature = plan.get("plan_signature")
    if (
        not isinstance(signature, str)
        or len(signature) != 64
        or any(char not in "0123456789abcdef" for char in signature)
    ):
        return None
    return hashlib.sha256(signature.encode("ascii")).hexdigest()


def _safe_blocker_counts(plan: Any, blocker_codes: Sequence[str]) -> dict[str, int]:
    """Return only allowlisted blocker codes, preserving signed-plan counts when safe."""
    safe_codes = sanitize_blocker_codes(blocker_codes)
    if not safe_codes:
        return {"BACKFILL_BLOCKER": 1}

    summary = plan.get("summary") if isinstance(plan, Mapping) and isinstance(plan.get("summary"), Mapping) else {}
    plan_counts = _safe_count_map(summary.get("blockers"), BLOCKER_CODES)
    return {code: plan_counts.get(code, 1) for code in safe_codes}


def _failure_result(
    plan: Any,
    error_code: str,
    *,
    phase: str,
    blocker_counts: Mapping[str, int] | None = None,
) -> ApplyResult:
    source_count, active_sources, anonymized_sources = _plan_source_counts(plan)
    summary = plan.get("summary") if isinstance(plan, Mapping) and isinstance(plan.get("summary"), Mapping) else {}
    resolved_blockers = dict(blocker_counts) if blocker_counts is not None else {error_code: 1}
    return ApplyResult(
        run_id=_safe_plan_run_id(plan),
        mode="apply",
        status="errore",
        actions={},
        contacts={},
        warning_counts=_safe_count_map(summary.get("warnings"), WARNING_CODES),
        blocker_counts=resolved_blockers,
        source_count=source_count,
        active_sources=active_sources,
        anonymized_sources=anonymized_sources,
        collisions=[],
        plan_digest=_safe_plan_digest(plan),
        error_code=error_code,
        error_phase=phase,
    )


def _safe_error_code(exc: BaseException) -> str:
    if isinstance(exc, PatientBackfillError):
        return sanitize_error_code(getattr(exc, "code", None))
    if isinstance(exc, IntegrityError):
        return "UNEXPECTED_INTEGRITY_ERROR"
    return "PATIENT_BACKFILL_ERROR"


def _success_audit_event(models: BackfillModels, plan: Mapping[str, Any], result: ApplyResult, now: datetime):
    details = {
        "run_id": result.run_id,
        "plan_version": plan["plan_version"],
        "source_count": result.source_count,
        "active_sources": result.active_sources,
        "anonymized_sources": result.anonymized_sources,
        "actions": result.actions,
        "contacts": result.contacts,
        "warning_counts": result.warning_counts,
        "plan_digest": result.plan_digest,
    }
    return models.RegistroEvento(
        categoria="pazienti_v2",
        esito="successo",
        messaggio="Backfill identità Pazienti 2.0 completato.",
        entita_tipo=None,
        entita_id=None,
        dettagli=json.dumps(details, ensure_ascii=False, sort_keys=True),
        creato_il=now,
    )


def _failure_audit_event(
    models: BackfillModels,
    run_id: str,
    code: str,
    phase: str,
    blocker_counts: Mapping[str, int],
    now: datetime,
):
    details = {
        "run_id": run_id,
        "error_code": code,
        "error_phase": phase,
        "blocker_codes": sorted(blocker_counts),
    }
    return models.RegistroEvento(
        categoria="pazienti_v2",
        esito="errore",
        messaggio="Backfill identità Pazienti 2.0 non completato.",
        entita_tipo=None,
        entita_id=None,
        dettagli=json.dumps(details, sort_keys=True),
        creato_il=now,
    )


def _assert_apply_plan_static(
    plan: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    key: bytes,
    code_revision: str,
    now: datetime,
) -> None:
    validate_plan_schema(dict(plan))
    verify_plan_signature(plan, key)
    expires = _parse_utc_iso(plan["expires_at"])
    if expires is None or now >= expires:
        raise ExpiredPlanError()
    if plan["code_revision"] != code_revision:
        raise CodeRevisionError()
    blocker_codes = set(plan["global_blockers"])
    for record in plan["records"]:
        blocker_codes.update(record["blockers"])
    if blocker_codes:
        raise BackfillBlockerError(sorted(blocker_codes))


def _compare_plan_to_current(
    plan: Mapping[str, Any],
    fresh_records: Sequence[dict[str, Any]],
    fresh_global_blockers: Sequence[str],
    fresh_collisions: Sequence[dict[str, Any]],
) -> None:
    if fresh_global_blockers:
        raise BackfillBlockerError(fresh_global_blockers)
    if list(fresh_collisions) != list(plan["collisions"]):
        raise StalePlanError()
    if len(fresh_records) != plan["source_count"]:
        raise StalePlanError()
    planned_by_id = {record["legacy_id"]: record for record in plan["records"]}
    if set(planned_by_id) != {record["legacy_id"] for record in fresh_records}:
        raise StalePlanError()
    for fresh in fresh_records:
        planned = planned_by_id[fresh["legacy_id"]]
        if fresh["source_fingerprint"] != planned["source_fingerprint"]:
            raise StalePlanError()
        if fresh["target_fingerprint"] != planned["target_fingerprint"]:
            raise StaleTargetError()
        for key_name in ("action", "warnings", "blockers"):
            if fresh[key_name] != planned[key_name]:
                raise StaleTargetError()


def _record_failure_audit_best_effort(
    engine: Engine,
    models: BackfillModels,
    *,
    run_id: str,
    error_code: str,
    error_phase: str,
    blocker_counts: Mapping[str, int],
    now: datetime,
) -> None:
    """Record a minimized post-rollback audit without leaking DB details."""
    try:
        with Session(engine) as audit_session:
            audit_session.add(
                _failure_audit_event(models, run_id, error_code, error_phase, blocker_counts, now)
            )
            audit_session.commit()
    except Exception as audit_exc:
        # Never log the DB message, statement, params or repr.  The local
        # exception variable is cleared by Python when this block exits.
        audit_error_type = type(audit_exc).__name__
        LOGGER.error(
            "PAZ-A2 failure audit unavailable run_id=%s error_code=%s error_phase=%s audit_error_type=%s",
            run_id,
            error_code,
            error_phase,
            audit_error_type,
        )


def _sanitized_exception_for_code(
    error_code: str,
    result: ApplyResult,
    *,
    blocker_codes: Sequence[str] = (),
) -> PatientBackfillError:
    mapping = {
        "INVALID_PLAN": InvalidPlanError,
        "EXPIRED_PLAN": ExpiredPlanError,
        "STALE_PLAN": StalePlanError,
        "STALE_TARGET": StaleTargetError,
        "PLAN_ENVIRONMENT_MISMATCH": EnvironmentMismatchError,
        "CODE_REVISION_MISMATCH": CodeRevisionError,
        "CONCURRENT_A2_APPLY": ConcurrentBackfillError,
    }
    if error_code in {"UNEXPECTED_INTEGRITY_ERROR", "PATIENT_BACKFILL_ERROR"}:
        exc: PatientBackfillError = ApplyExecutionError(error_code, result)
    elif error_code == "BACKFILL_BLOCKER":
        exc = BackfillBlockerError(blocker_codes or ("BACKFILL_BLOCKER",))
    elif error_code in mapping:
        exc = mapping[error_code]()
    elif error_code in ERROR_CODES:
        exc = PatientBackfillError(code=error_code)
    else:
        exc = ApplyExecutionError("PATIENT_BACKFILL_ERROR", result)
    exc.failure_result = result
    if isinstance(exc, ApplyExecutionError):
        exc.result = result
    return exc


def apply_backfill_plan(
    engine: Engine,
    models: BackfillModels,
    plan: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    now: datetime | None = None,
    code_revision: str | None = None,
    key: bytes | None = None,
) -> ApplyResult:
    apply_now = now or utc_now_naive()
    phase = "preflight"
    failure_code: str | None = None
    failure_result: ApplyResult | None = None
    failure_blocker_codes: tuple[str, ...] = ()
    failure_blocker_counts: dict[str, int] | None = None

    try:
        plan_key = key or get_plan_key(config)
        revision = code_revision or resolve_code_revision(config)
        _assert_apply_plan_static(
            plan,
            config=config,
            key=plan_key,
            code_revision=revision,
            now=apply_now,
        )

        run_id = str(plan["run_id"])
        actions = {code: 0 for code in ACTION_CODES}
        contact_stats = {
            "created": 0,
            "archived": 0,
            "reactivated": 0,
            "privacy_deleted": 0,
        }
        warning_counts = dict(plan["summary"].get("warnings", {}))
        blocker_counts: dict[str, int] = {}
        digest = _plan_digest(plan)

        phase = "lock"
        with apply_session(engine) as session:
            phase = "revalidation"
            current_alembic = read_alembic_revision(session)
            if current_alembic != plan["alembic_revision"]:
                raise PatientBackfillError(code="A1_NOT_READY")
            current_env = database_environment_fingerprint(
                engine,
                str(config.get("APP_ENV") or "development"),
                plan_key,
                connection=session.connection(),
            )
            if not hmac.compare_digest(current_env, plan["environment_fingerprint"]):
                raise EnvironmentMismatchError()

            fresh_records, _fresh_summary, fresh_global_blockers, fresh_collisions = analyze_backfill_state(
                session,
                models,
                key=plan_key,
                now=apply_now,
            )
            _compare_plan_to_current(plan, fresh_records, fresh_global_blockers, fresh_collisions)

            phase = "write"
            sources = _load_sources(session, models)
            people_by_legacy = _load_people_by_legacy(session, models)
            for source in sources:
                assessment = analyze_legacy_source(source, apply_now)
                person = people_by_legacy.get(int(source.id))
                person, action = _apply_source_projection(
                    session,
                    models,
                    source,
                    assessment,
                    person,
                    now=apply_now,
                    contact_stats=contact_stats,
                )
                people_by_legacy[int(source.id)] = person
                actions[action] += 1

            session.flush()
            phase_blockers = _global_phase_blockers(session, models)
            if phase_blockers:
                raise BackfillBlockerError(sorted(phase_blockers))

            source_count, active_sources, anonymized_sources = _plan_source_counts(plan)
            result = ApplyResult(
                run_id=run_id,
                mode="apply",
                status="successo",
                actions={item: value for item, value in actions.items() if value},
                contacts={item: value for item, value in contact_stats.items() if value},
                warning_counts=warning_counts,
                blocker_counts=blocker_counts,
                source_count=source_count,
                active_sources=active_sources,
                anonymized_sources=anonymized_sources,
                collisions=list(plan["collisions"]),
                plan_digest=digest,
            )

            phase = "audit"
            session.add(_success_audit_event(models, plan, result, apply_now))
            session.flush()
            session.commit()
            return result
    except Exception as caught:
        # Extract only stable, allowlisted primitives while the original
        # exception is alive. Never retain the original exception object.
        failure_code = _safe_error_code(caught)
        if isinstance(caught, BackfillBlockerError):
            failure_blocker_codes = tuple(caught.blocker_codes)
            failure_blocker_counts = _safe_blocker_counts(plan, failure_blocker_codes)
        failure_result = _failure_result(
            plan,
            failure_code,
            phase=phase,
            blocker_counts=failure_blocker_counts,
        )

    # Deliberately outside the primary except block: the caught DB exception
    # is no longer the active exception, so the sanitized exception raised
    # below receives neither __context__ nor __cause__ pointing to patient data.
    assert failure_code is not None and failure_result is not None
    _record_failure_audit_best_effort(
        engine,
        models,
        run_id=failure_result.run_id,
        error_code=failure_code,
        error_phase=phase,
        blocker_counts=failure_result.blocker_counts,
        now=apply_now,
    )
    sanitized = _sanitized_exception_for_code(
        failure_code,
        failure_result,
        blocker_codes=failure_blocker_codes,
    )
    raise sanitized


def dry_run_result(plan: Mapping[str, Any]) -> ApplyResult:
    validate_plan_schema(dict(plan))
    blocker_counts = dict(plan["summary"].get("blockers", {}))
    source_count, active_sources, anonymized_sources = _plan_source_counts(plan)
    return ApplyResult(
        run_id=str(plan["run_id"]),
        mode="dry-run",
        status="bloccato" if blocker_counts else "pronto",
        actions=dict(plan["summary"].get("actions", {})),
        contacts=dict(plan["summary"].get("contacts", {})),
        warning_counts=dict(plan["summary"].get("warnings", {})),
        blocker_counts=blocker_counts,
        source_count=source_count,
        active_sources=active_sources,
        anonymized_sources=anonymized_sources,
        collisions=list(plan["collisions"]),
        plan_digest=_plan_digest(plan),
    )


__all__ = [
    "ACTION_CODES",
    "ApplyExecutionError",
    "ApplyResult",
    "BackfillBlockerError",
    "BackfillModels",
    "BLOCKER_CODES",
    "ConcurrentBackfillError",
    "DEFAULT_PLAN_TTL_SECONDS",
    "EnvironmentMismatchError",
    "ExpiredPlanError",
    "InvalidPlanError",
    "PLAN_PURPOSE",
    "PLAN_VERSION",
    "PatientBackfillError",
    "paths_equivalent",
    "StalePlanError",
    "StaleTargetError",
    "WARNING_CODES",
    "analyze_backfill_state",
    "analyze_legacy_source",
    "apply_backfill_plan",
    "build_backfill_plan",
    "canonical_json_bytes",
    "database_environment_fingerprint",
    "delete_plan_file",
    "dry_run_result",
    "get_plan_key",
    "read_plan_file_secure",
    "resolve_code_revision",
    "sign_plan",
    "validate_plan_schema",
    "verify_plan_signature",
    "write_plan_file",
    "write_report_file",
]
