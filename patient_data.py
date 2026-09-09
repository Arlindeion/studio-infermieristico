"""Validation and canonicalization helpers for the proposed Patients 2.0 schema.

PAZ-A1 keeps this module independent from Flask and SQLAlchemy so the same
rules can be reused by future backfill code without importing the web app.
Only validation required by the additive A1 schema lives here; duplicate and
merge payload logic is deliberately deferred until those workflows exist.
"""

from __future__ import annotations

import re
import unicodedata


MAX_NAME_LENGTH = 100
MAX_TAX_CODE_LENGTH = 32
MAX_EMAIL_LENGTH = 254
MIN_PHONE_DIGITS = 6
MAX_PHONE_DIGITS = 15

ALLOWED_SEX_CODES = frozenset({"F", "M"})
ALLOWED_RELATIONSHIP_ROLES = frozenset(
    {"madre", "padre", "tutore", "affidatario", "caregiver", "altro"}
)

_PHONE_FORMAT_RE = re.compile(r"^(?:\+|00)?[0-9\s()./\-]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PatientDataValidationError(ValueError):
    """Raised when a value cannot be safely stored in the Patients 2.0 schema."""


def _nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def normalize_patient_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", _nfkc(value).strip())
    if not normalized:
        return None
    if len(normalized) > MAX_NAME_LENGTH:
        raise PatientDataValidationError(
            f"Il nome supera il limite di {MAX_NAME_LENGTH} caratteri."
        )
    return normalized


def normalize_tax_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "", _nfkc(value)).upper().strip()
    if not normalized:
        return None
    if len(normalized) > MAX_TAX_CODE_LENGTH:
        raise PatientDataValidationError(
            f"Il codice fiscale supera il limite di {MAX_TAX_CODE_LENGTH} caratteri."
        )
    return normalized


def normalize_email_address(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _nfkc(value).strip().casefold()
    if not normalized:
        return None
    if len(normalized) > MAX_EMAIL_LENGTH or not _EMAIL_RE.fullmatch(normalized):
        raise PatientDataValidationError("Indirizzo email non valido.")
    local_part, domain = normalized.rsplit("@", 1)
    if len(local_part) > 64 or len(domain) > 253:
        raise PatientDataValidationError("Indirizzo email non valido.")
    return normalized


def normalize_phone_number(value: str | None) -> str | None:
    """Normalize a phone number without silently accepting malformed input.

    The length limit is applied to the *normalized subscriber/country digits*.
    In particular the international access prefix ``00`` is removed before the
    E.164-style 15-digit limit is checked, so ``00`` itself does not consume two
    digits from that limit.
    """

    if value is None:
        return None
    display_value = _nfkc(value).strip()
    if not display_value:
        return None
    if not _PHONE_FORMAT_RE.fullmatch(display_value):
        raise PatientDataValidationError("Numero di telefono non valido.")

    if display_value.startswith("00"):
        normalized_source = display_value[2:]
        international = True
    elif display_value.startswith("+"):
        normalized_source = display_value[1:]
        international = True
    else:
        normalized_source = display_value
        international = False

    digits = re.sub(r"\D", "", normalized_source)
    if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
        raise PatientDataValidationError("Numero di telefono non valido.")

    return f"+{digits}" if international else digits


def validate_sex_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _nfkc(value).strip().upper()
    if not normalized:
        return None
    if normalized not in ALLOWED_SEX_CODES:
        raise PatientDataValidationError("Valore del sesso anagrafico non ammesso.")
    return normalized


def validate_relationship_role(value: str) -> str:
    normalized = _nfkc(value).strip().casefold()
    if normalized not in ALLOWED_RELATIONSHIP_ROLES:
        raise PatientDataValidationError("Ruolo della relazione non ammesso.")
    return normalized
