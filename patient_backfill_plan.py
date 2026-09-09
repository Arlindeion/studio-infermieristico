"""Plan contract, signing and runtime identity helpers for PAZ-A2.

This module contains no backfill writes. It owns the signed-plan contract and
runtime/database identity checks so the service layer can stay focused on
analysis and transactional reconciliation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import subprocess
import uuid
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session

from patient_backfill_artifacts import canonical_json_bytes

PLAN_VERSION = 1
PLAN_PURPOSE = "PAZ-A2-identity-backfill"
PLAN_KEY_CONTEXT = b"PAZ-A2-plan-v1"
DEFAULT_PLAN_TTL_SECONDS = 3600

ACTION_CODES = frozenset({"create", "update", "anonymize", "already_synced"})
WARNING_CODES = frozenset(
    {
        "INVALID_PHONE",
        "INVALID_EMAIL",
        "INVALID_TAX_CODE",
        "LEGACY_CHILD_FIELDS_PRESENT",
        "LEGACY_NOTE_PRESENT",
        "DUPLICATE_NORMALIZED_TAX_CODE",
        "DUPLICATE_NORMALIZED_PHONE",
        "DUPLICATE_NORMALIZED_EMAIL",
        "MISSING_LEGACY_NAME",
    }
)
BLOCKER_CODES = frozenset(
    {
        "A1_NOT_READY",
        "INVALID_PLAN",
        "EXPIRED_PLAN",
        "STALE_PLAN",
        "STALE_TARGET",
        "PLAN_ENVIRONMENT_MISMATCH",
        "CODE_REVISION_UNKNOWN",
        "CODE_REVISION_MISMATCH",
        "UNSTABLE_PLAN_KEY",
        "ANONYMIZED_SOURCE_HAS_RESIDUAL_PII",
        "ANONYMIZATION_STATE_INCONSISTENT",
        "INVALID_ANONYMIZATION_TIMESTAMP",
        "ANONYMIZATION_REVERSED",
        "TARGET_OUT_OF_PHASE_CHANGE",
        "PRACTICE_V2_FK_ALREADY_POPULATED",
        "UNEXPECTED_V2_DOMAIN_DATA",
        "CONCURRENT_A2_APPLY",
        "UNEXPECTED_INTEGRITY_ERROR",
    }
)
GENERAL_ERROR_CODES = frozenset({"PATIENT_BACKFILL_ERROR", "BACKFILL_BLOCKER"})
ERROR_CODES = BLOCKER_CODES | GENERAL_ERROR_CODES


def sanitize_error_code(value: Any, *, default: str = "PATIENT_BACKFILL_ERROR") -> str:
    """Return a stable allowlisted error code without exposing arbitrary input."""
    if isinstance(value, str) and value in ERROR_CODES:
        return value
    return default if default in ERROR_CODES else "PATIENT_BACKFILL_ERROR"


def sanitize_blocker_codes(values: Any) -> tuple[str, ...]:
    """Return sorted, unique blocker codes from the closed PAZ-A2 allowlist."""
    if isinstance(values, str):
        candidates = (values,)
    else:
        try:
            candidates = tuple(values)
        except TypeError:
            candidates = ()
    return tuple(sorted({value for value in candidates if isinstance(value, str) and value in BLOCKER_CODES}))


_REQUIRED_PLAN_KEYS = frozenset(
    {
        "plan_version", "purpose", "run_id", "generated_at", "expires_at",
        "code_revision", "alembic_revision", "environment_fingerprint",
        "source_count", "global_blockers", "collisions", "records",
        "summary", "plan_signature",
    }
)
_REQUIRED_RECORD_KEYS = frozenset(
    {
        "legacy_id", "source_updated_at", "source_anonymized_at", "action",
        "warnings", "blockers", "source_fingerprint", "target_fingerprint",
    }
)
_REQUIRED_SUMMARY_KEYS = frozenset(
    {"actions", "warnings", "blockers", "contacts", "active_sources", "anonymized_sources"}
)

class PatientBackfillError(Exception):
    code = "PATIENT_BACKFILL_ERROR"

    def __init__(self, message: str | None = None, *, code: str | None = None):
        resolved_code = code or self.code
        # Backward-compatible safety for the few generic call sites that pass
        # a stable code as the first positional argument.
        if code is None and isinstance(message, str) and message in ERROR_CODES:
            resolved_code = message
            message = None
        self.code = sanitize_error_code(resolved_code)
        self.failure_result: Any | None = None
        super().__init__(message or self.code)


class InvalidPlanError(PatientBackfillError):
    code = "INVALID_PLAN"


class ExpiredPlanError(PatientBackfillError):
    code = "EXPIRED_PLAN"


class StalePlanError(PatientBackfillError):
    code = "STALE_PLAN"


class StaleTargetError(PatientBackfillError):
    code = "STALE_TARGET"


class EnvironmentMismatchError(PatientBackfillError):
    code = "PLAN_ENVIRONMENT_MISMATCH"


class CodeRevisionError(PatientBackfillError):
    code = "CODE_REVISION_MISMATCH"


class ConcurrentBackfillError(PatientBackfillError):
    code = "CONCURRENT_A2_APPLY"


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _datetime_to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise InvalidPlanError("Timestamp non valido.")
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return aware.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise InvalidPlanError("Timestamp piano non valido.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InvalidPlanError("Timestamp piano non valido.") from None
    if parsed.utcoffset() != timedelta(0):
        raise InvalidPlanError("Timestamp piano non UTC.")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _json_default(value: Any):
    if isinstance(value, datetime):
        return _datetime_to_utc_iso(value)
    raise TypeError(f"Tipo non serializzabile: {type(value).__name__}")


def _hmac_hex(key: bytes, value: Any) -> str:
    return hmac.new(key, canonical_json_bytes(value), hashlib.sha256).hexdigest()


def get_plan_key(config: Mapping[str, Any]) -> bytes:
    secret = config.get("SECRET_KEY")
    if config.get("SECRET_KEY_IS_EPHEMERAL"):
        raise PatientBackfillError("UNSTABLE_PLAN_KEY")
    if not isinstance(secret, str) or len(secret) < 32:
        raise PatientBackfillError("UNSTABLE_PLAN_KEY")
    return hmac.new(secret.encode("utf-8"), PLAN_KEY_CONTEXT, hashlib.sha256).digest()


def sign_plan(unsigned_plan: Mapping[str, Any], key: bytes) -> str:
    return _hmac_hex(key, unsigned_plan)


def verify_plan_signature(plan: Mapping[str, Any], key: bytes) -> None:
    supplied = plan.get("plan_signature")
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise InvalidPlanError("Firma piano non valida.")
    unsigned = dict(plan)
    unsigned.pop("plan_signature", None)
    expected = sign_plan(unsigned, key)
    if not hmac.compare_digest(supplied, expected):
        raise InvalidPlanError("Firma piano non valida.")


def _require_exact_keys(value: Mapping[str, Any], expected: frozenset[str]) -> None:
    if set(value) != set(expected):
        raise InvalidPlanError("Schema piano non valido.")


def _require_plain_int(value: Any, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidPlanError("Intero piano non valido.")
    if minimum is not None and value < minimum:
        raise InvalidPlanError("Intero piano fuori intervallo.")
    return value


def _require_hex_digest(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise InvalidPlanError("Digest piano non valido.")
    if any(char not in "0123456789abcdef" for char in value):
        raise InvalidPlanError("Digest piano non valido.")
    return value


def _validate_code_list(values: Any, allowed: frozenset[str]) -> list[str]:
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise InvalidPlanError("Lista codici piano non valida.")
    if len(values) != len(set(values)) or values != sorted(values):
        raise InvalidPlanError("Lista codici piano non canonica.")
    if any(item not in allowed for item in values):
        raise InvalidPlanError("Codice piano non ammesso.")
    return values


def _validate_count_map(value: Any, allowed_keys: frozenset[str]) -> dict[str, int]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise InvalidPlanError("Conteggi piano non validi.")
    if any(k not in allowed_keys for k in value):
        raise InvalidPlanError("Conteggio piano non ammesso.")
    for count in value.values():
        _require_plain_int(count, minimum=0)
    return value


def validate_plan_schema(raw_plan: Any) -> dict[str, Any]:
    if not isinstance(raw_plan, dict):
        raise InvalidPlanError("Il piano deve essere un oggetto JSON.")
    _require_exact_keys(raw_plan, _REQUIRED_PLAN_KEYS)

    if raw_plan["plan_version"] != PLAN_VERSION or raw_plan["purpose"] != PLAN_PURPOSE:
        raise InvalidPlanError("Versione o scopo piano non ammessi.")
    try:
        uuid.UUID(str(raw_plan["run_id"]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidPlanError("Run ID non valido.") from None

    generated = _parse_utc_iso(raw_plan["generated_at"])
    expires = _parse_utc_iso(raw_plan["expires_at"])
    if generated is None or expires is None or expires <= generated:
        raise InvalidPlanError("Finestra temporale piano non valida.")

    for key_name in ("code_revision", "alembic_revision"):
        if not isinstance(raw_plan[key_name], str) or not raw_plan[key_name].strip():
            raise InvalidPlanError("Revisione piano non valida.")
    _require_hex_digest(raw_plan["environment_fingerprint"])
    _require_plain_int(raw_plan["source_count"], minimum=0)
    _validate_code_list(raw_plan["global_blockers"], BLOCKER_CODES)
    collisions = raw_plan["collisions"]
    if not isinstance(collisions, list):
        raise InvalidPlanError("Collisioni piano non valide.")
    allowed_collision_codes = {
        "DUPLICATE_NORMALIZED_TAX_CODE",
        "DUPLICATE_NORMALIZED_PHONE",
        "DUPLICATE_NORMALIZED_EMAIL",
    }
    canonical_collisions = []
    for collision in collisions:
        if not isinstance(collision, dict) or set(collision) != {"code", "legacy_ids"}:
            raise InvalidPlanError("Collisione piano non valida.")
        if collision["code"] not in allowed_collision_codes:
            raise InvalidPlanError("Collisione piano non ammessa.")
        ids = collision["legacy_ids"]
        if not isinstance(ids, list) or len(ids) < 2:
            raise InvalidPlanError("ID collisione non validi.")
        parsed_ids = [_require_plain_int(item, minimum=1) for item in ids]
        if parsed_ids != sorted(parsed_ids) or len(parsed_ids) != len(set(parsed_ids)):
            raise InvalidPlanError("ID collisione non canonici.")
        canonical_collisions.append((collision["code"], parsed_ids))
    if canonical_collisions != sorted(canonical_collisions):
        raise InvalidPlanError("Ordine collisioni non canonico.")

    records = raw_plan["records"]
    if not isinstance(records, list):
        raise InvalidPlanError("Records piano non validi.")
    if len(records) != raw_plan["source_count"]:
        raise InvalidPlanError("Conteggio sorgenti incoerente.")

    legacy_ids: list[int] = []
    for record in records:
        if not isinstance(record, dict):
            raise InvalidPlanError("Record piano non valido.")
        _require_exact_keys(record, _REQUIRED_RECORD_KEYS)
        legacy_id = _require_plain_int(record["legacy_id"], minimum=1)
        legacy_ids.append(legacy_id)
        _parse_utc_iso(record["source_updated_at"]) if record["source_updated_at"] else None
        _parse_utc_iso(record["source_anonymized_at"]) if record["source_anonymized_at"] else None
        if record["action"] not in ACTION_CODES:
            raise InvalidPlanError("Azione piano non valida.")
        _validate_code_list(record["warnings"], WARNING_CODES)
        _validate_code_list(record["blockers"], BLOCKER_CODES)
        _require_hex_digest(record["source_fingerprint"])
        _require_hex_digest(record["target_fingerprint"])

    if legacy_ids != sorted(legacy_ids) or len(legacy_ids) != len(set(legacy_ids)):
        raise InvalidPlanError("Ordine o unicità ID legacy non validi.")

    summary = raw_plan["summary"]
    if not isinstance(summary, dict):
        raise InvalidPlanError("Summary piano non valida.")
    _require_exact_keys(summary, _REQUIRED_SUMMARY_KEYS)
    _validate_count_map(summary["actions"], ACTION_CODES)
    _validate_count_map(summary["warnings"], WARNING_CODES)
    _validate_count_map(summary["blockers"], BLOCKER_CODES)
    contact_keys = frozenset(
        {
            "phone_expected",
            "email_expected",
            "phone_invalid",
            "email_invalid",
        }
    )
    _validate_count_map(summary["contacts"], contact_keys)
    _require_plain_int(summary["active_sources"], minimum=0)
    _require_plain_int(summary["anonymized_sources"], minimum=0)
    _require_hex_digest(raw_plan["plan_signature"])
    return raw_plan


def resolve_code_revision(config: Mapping[str, Any], repo_path: str | os.PathLike | None = None) -> str:
    candidates = [
        config.get("APP_BUILD_REVISION"),
        os.environ.get("APP_BUILD_REVISION"),
        os.environ.get("RENDER_GIT_COMMIT"),
        os.environ.get("GIT_COMMIT"),
        os.environ.get("COMMIT_SHA"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    cwd = str(repo_path or Path(__file__).resolve().parent)
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        raise PatientBackfillError("CODE_REVISION_UNKNOWN")
    revision = proc.stdout.strip()
    if not revision:
        raise PatientBackfillError("CODE_REVISION_UNKNOWN")
    return revision


def _canonical_database_identity(url: URL, app_env: str) -> dict[str, Any]:
    driver = url.get_backend_name()
    if driver == "sqlite":
        database = url.database or ":memory:"
        if database != ":memory:":
            database = str(Path(database).expanduser().resolve())
        return {
            "app_env": app_env,
            "dialect": "sqlite",
            "database": database,
        }

    if driver == "postgresql":
        return {
            "app_env": app_env,
            "dialect": "postgresql",
            "host": (url.host or "<default>").casefold(),
            "port": url.port or 5432,
            "database": url.database or "<default>",
        }

    return {
        "app_env": app_env,
        "dialect": driver,
        "host": (url.host or "<default>").casefold(),
        "port": url.port,
        "database": url.database or "<default>",
    }


def database_environment_fingerprint(
    engine: Engine,
    app_env: str,
    key: bytes,
    *,
    connection: Any | None = None,
) -> str:
    identity = _canonical_database_identity(engine.url, app_env)
    if identity.get("dialect") == "postgresql":
        schema = None
        try:
            if connection is not None:
                schema = connection.execute(text("SELECT current_schema()")).scalar_one_or_none()
            elif hasattr(engine, "connect"):
                with engine.connect() as owned_connection:
                    schema = owned_connection.execute(text("SELECT current_schema()")).scalar_one_or_none()
        except Exception:
            schema = None
        identity["schema"] = schema or "<default>"
    return _hmac_hex(key, identity)


def read_alembic_revision(session: Session) -> str:
    try:
        rows = session.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars().all()
    except Exception as exc:
        raise PatientBackfillError("A1_NOT_READY") from None
    if len(rows) != 1 or not rows[0]:
        raise PatientBackfillError("A1_NOT_READY")
    return str(rows[0])
