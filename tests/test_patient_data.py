import pytest

from patient_data import (
    PatientDataValidationError,
    normalize_email_address,
    normalize_patient_name,
    normalize_phone_number,
    normalize_tax_code,
    validate_relationship_role,
    validate_sex_code,
)


def test_normalize_patient_name_preserves_case_apostrophes_and_hyphens():
    assert normalize_patient_name("  D'Angelo   De-Luca ") == "D'Angelo De-Luca"
    assert normalize_patient_name("\u212bngela") == "Ångela"
    assert normalize_patient_name("   ") is None


def test_normalize_tax_code_is_nfkc_trimmed_and_uppercase_without_formal_validation():
    assert normalize_tax_code(" rssmra80a01h501u ") == "RSSMRA80A01H501U"
    assert normalize_tax_code("  ") is None
    with pytest.raises(PatientDataValidationError):
        normalize_tax_code("X" * 33)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mario.Rossi@Example.IT", "mario.rossi@example.it"),
        ("  test@example.invalid ", "test@example.invalid"),
        ("", None),
    ],
)
def test_normalize_email_address(raw, expected):
    assert normalize_email_address(raw) == expected


@pytest.mark.parametrize("raw", ["abc1", "mario@", "a b@example.it", "@example.it", "a@b"])
def test_email_or_phone_garbage_is_rejected(raw):
    fn = normalize_email_address if "@" in raw or "example" in raw else normalize_phone_number
    with pytest.raises(PatientDataValidationError):
        fn(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("333 123 4567", "3331234567"),
        ("+39 333-123-4567", "+393331234567"),
        ("0039 333 123 4567", "+393331234567"),
        ("085/123456", "085123456"),
        # 15 cifre effettive dopo il prefisso internazionale 00: deve essere valido.
        ("00123456789012345", "+123456789012345"),
    ],
)
def test_normalize_phone_number_accepts_only_known_formatting(raw, expected):
    assert normalize_phone_number(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "123",
        "001234",  # dopo 00 restano solo 4 cifre
        "abc1",
        "+39ABC123",
        "++393331234567",
        "3" * 16,
        "00" + ("1" * 16),
    ],
)
def test_normalize_phone_number_rejects_malformed_or_implausible_values(raw):
    with pytest.raises(PatientDataValidationError):
        normalize_phone_number(raw)


def test_sex_code_is_limited_and_nullable():
    assert validate_sex_code(None) is None
    assert validate_sex_code("f") == "F"
    assert validate_sex_code("M") == "M"
    with pytest.raises(PatientDataValidationError):
        validate_sex_code("other")


def test_caregiver_is_descriptive_role_but_not_an_authorization():
    assert validate_relationship_role("Caregiver") == "caregiver"
    with pytest.raises(PatientDataValidationError):
        validate_relationship_role("amministratore")
