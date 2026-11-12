"""Conservative Indian registration candidate normalization and format checks."""
import re

INDIAN_REGISTRATION_PATTERN = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$")
BH_REGISTRATION_PATTERN = re.compile(r"^\d{2}BH\d{4}[A-Z]{1,2}$")


def normalize_registration_candidate(raw_text: str | None) -> tuple[str, str]:
    """Remove display separators only; never substitute or infer characters."""
    raw = raw_text or ""
    candidate = "".join(character for character in raw.upper() if character.isalnum())
    if not candidate:
        return "", "empty"
    status = "valid_indian_format" if (
        INDIAN_REGISTRATION_PATTERN.fullmatch(candidate)
        or BH_REGISTRATION_PATTERN.fullmatch(candidate)
    ) else "invalid_indian_format"
    return candidate, status
