"""Convert raw LLM output into the final response shape.

Responsibilities:
- Coerce amount fields to integers (strip currency, separators, decimals).
- Normalise date fields to DD/MM/YYYY.
- Strip provider_name when it contains "Fullerton Health".
- Coerce mc_days to int.

Postprocess never raises on bad data — it just returns null for the field.
Validation happens in the next stage; keeping this one defensive means the
Pydantic validator sees a clean dict shape.
"""
from __future__ import annotations

import re
from typing import Any

from app.schemas import DOC_TYPE_REGISTRY
from app.schemas.base import DocumentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


AMOUNT_FIELDS = {
    "total_amount_paid",
    "total_approved_amount",
    "total_requested_amount",
    "tax_amount",
    "total_amount",
}

DATE_FIELDS = {
    "claimant_date_of_birth",
    "discharge_date_time",
    "submission_date_time",
    "date_of_mc",
}

INTEGER_FIELDS = {"mc_days"}

PROVIDER_NAME_FIELDS = {"provider_name"}

FULLERTON_PATTERN = re.compile(r"fullerton\s*health", re.IGNORECASE)


def normalize_amount(value: Any) -> int | None:
    """Strip currency symbols, separators, decimals; return integer."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def normalize_integer(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+", value)
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                return None
    return None


_DATE_PATTERNS = [
    # (regex, (year, month, day) group indices)
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"), ("y3", "m2", "d1")),
    (re.compile(r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b"), ("y1", "m2", "d3")),
    # "12 March 1985" / "12 Mar 1985"
    (
        re.compile(
            r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b"
        ),
        ("y3", "mname", "d1"),
    ),
]

_MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def normalize_date(value: Any) -> str | None:
    """Return DD/MM/YYYY or None if unparseable.

    Conservative: when the pattern is ambiguous (e.g. 03/04/2024) we trust the
    LLM's output ordering, which the prompt instructs to be DD/MM/YYYY already.
    Reorders only when the pattern is unambiguously not DD/MM/YYYY (4-digit
    year first, or month-name form).
    """
    if value is None or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None

    for pattern, role_map in _DATE_PATTERNS:
        m = pattern.search(s)
        if not m:
            continue

        try:
            if "mname" in role_map:
                day = int(m.group(1))
                month_name = m.group(2).lower()
                year = int(m.group(3))
                month = _MONTH_NAMES.get(month_name)
                if month is None:
                    continue
            elif role_map[0] == "y1":
                year = int(m.group(1))
                month = int(m.group(2))
                day = int(m.group(3))
            else:
                day = int(m.group(1))
                month = int(m.group(2))
                year = int(m.group(3))

            if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
                continue
            return f"{day:02d}/{month:02d}/{year:04d}"
        except (ValueError, IndexError):
            continue

    return None


def filter_provider_name(value: Any) -> str | None:
    if value is None or not isinstance(value, str):
        return None
    if FULLERTON_PATTERN.search(value):
        return None
    cleaned = value.strip()
    return cleaned or None


def postprocess(raw: dict[str, Any], doc_type: DocumentType) -> dict[str, Any]:
    """Apply field normalisers, return a dict with all schema keys populated."""
    spec = DOC_TYPE_REGISTRY[doc_type]
    schema_fields = spec.pydantic_model.model_fields.keys()

    out: dict[str, Any] = {}
    for field in schema_fields:
        value = raw.get(field)
        if field in AMOUNT_FIELDS:
            out[field] = normalize_amount(value)
        elif field in DATE_FIELDS:
            out[field] = normalize_date(value)
        elif field in INTEGER_FIELDS:
            out[field] = normalize_integer(value)
        elif field in PROVIDER_NAME_FIELDS:
            out[field] = filter_provider_name(value)
        elif field == "signature_presence":
            out[field] = bool(value) if value is not None else False
        else:
            if value is None:
                out[field] = None
            elif isinstance(value, str):
                stripped = value.strip()
                out[field] = stripped or None
            else:
                out[field] = value
    return out
