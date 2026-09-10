"""Application services for Patients 2.0.

The module deliberately stays independent from Flask. It contains patient-domain
logic that would otherwise make ``app.py`` grow further: safe identity lookup
and list-level practice aggregation. ORM models and the active SQLAlchemy
session are passed explicitly so the service stays testable while the existing
Italian persistence schema remains unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from patient_data import PatientDataValidationError, normalize_tax_code


class AmbiguousPatientMatchError(PatientDataValidationError):
    """Raised when a supposedly identifying lookup matches multiple patients."""

    def __init__(self) -> None:
        super().__init__(
            "Il codice fiscale corrisponde a più anagrafiche. "
            "Risolvi il duplicato manualmente prima di collegare la pratica."
        )


def find_active_patient_by_tax_code(
    session: Session,
    patient_model: Any,
    tax_code: str | None,
) -> Any | None:
    """Return one active patient for a tax code, never an arbitrary match.

    ``Persona.codice_fiscale`` is indexed but intentionally not unique because
    historical/imported data can contain collisions. A tax-code lookup is safe
    only when exactly one active, identifiable row matches.
    """

    normalized_tax_code = normalize_tax_code(tax_code)
    if not normalized_tax_code:
        return None

    matches = list(
        session.scalars(
            select(patient_model)
            .where(
                func.upper(patient_model.codice_fiscale) == normalized_tax_code,
                patient_model.dati_anonimizzati_il.is_(None),
                patient_model.stato == "attiva",
            )
            .order_by(patient_model.id)
            .limit(2)
        ).all()
    )
    if len(matches) > 1:
        raise AmbiguousPatientMatchError()
    return matches[0] if matches else None


def load_patient_practice_counts(
    session: Session,
    patients: Iterable[Any],
    *,
    appointment_model: Any,
    sleep_call_model: Any,
    registration_model: Any,
    legacy_link_model: Any,
) -> Mapping[int, int]:
    """Load practice counts for a patient list with a fixed number of queries.

    The result mirrors the de-duplication semantics of the detail view: direct
    Patients 2.0 foreign keys are counted first, then read-only legacy mappings
    are added only when the same existing practice has not already been seen
    through v2. The number of SQL queries does not grow with the patient count.
    """

    patient_list = list(patients)
    patient_ids = [patient.id for patient in patient_list if patient.id is not None]
    if not patient_ids:
        return {}

    practice_keys: dict[int, set[tuple[str, int]]] = defaultdict(set)
    for patient_id in patient_ids:
        practice_keys[int(patient_id)]

    direct_sources = (
        ("Appuntamento", appointment_model.persona_id, appointment_model.id),
        ("CallSonno", sleep_call_model.persona_id, sleep_call_model.id),
        ("IscrizioneCorso", registration_model.persona_v2_id, registration_model.id),
    )
    for practice_type, patient_column, practice_id_column in direct_sources:
        rows = session.execute(
            select(patient_column, practice_id_column).where(
                patient_column.in_(patient_ids)
            )
        ).all()
        for patient_id, practice_id in rows:
            practice_keys[int(patient_id)].add((practice_type, int(practice_id)))

    legacy_to_patient = {
        int(patient.legacy_persona_corso_id): int(patient.id)
        for patient in patient_list
        if patient.id is not None and patient.legacy_persona_corso_id is not None
    }
    if legacy_to_patient:
        legacy_ids = tuple(legacy_to_patient)
        registration_rows = session.execute(
            select(registration_model.persona_id, registration_model.id).where(
                registration_model.persona_id.in_(legacy_ids)
            )
        ).all()
        for legacy_id, practice_id in registration_rows:
            patient_id = legacy_to_patient.get(int(legacy_id))
            if patient_id is not None:
                practice_keys[patient_id].add(("IscrizioneCorso", int(practice_id)))

        link_rows = session.execute(
            select(
                legacy_link_model.persona_id,
                legacy_link_model.entita_tipo,
                legacy_link_model.entita_id,
            ).where(
                legacy_link_model.persona_id.in_(legacy_ids),
                legacy_link_model.entita_tipo.in_(("Appuntamento", "CallSonno")),
            )
        ).all()

        links_by_type: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for legacy_id, practice_type, practice_id in link_rows:
            patient_id = legacy_to_patient.get(int(legacy_id))
            if patient_id is not None:
                links_by_type[str(practice_type)].append(
                    (patient_id, int(practice_id))
                )

        legacy_targets = {
            "Appuntamento": appointment_model,
            "CallSonno": sleep_call_model,
        }
        for practice_type, model in legacy_targets.items():
            linked = links_by_type.get(practice_type, [])
            if not linked:
                continue
            linked_ids = {practice_id for _, practice_id in linked}
            existing_ids = set(
                session.scalars(
                    select(model.id).where(model.id.in_(linked_ids))
                ).all()
            )
            for patient_id, practice_id in linked:
                if practice_id in existing_ids:
                    practice_keys[patient_id].add((practice_type, practice_id))

    return {
        patient_id: len(keys)
        for patient_id, keys in practice_keys.items()
    }
