"""Validate post-processed extraction output.

Three classes of checks:
1. Pydantic schema — type correctness (str/int/bool/None).
2. Required-field presence — drives the failed/degraded distinction.
3. Cross-check vs. raw PDF text (when available) — catches LLM hallucinations
   on amount/date/icd_code fields by checking that the extracted value (or its
   raw form before normalization) plausibly appears in the source text.

The validator returns a structured ValidationReport rather than raising.
The orchestrator inspects the report to decide retry vs. failure-store routing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas import DOC_TYPE_REGISTRY
from app.schemas.base import DocumentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


CROSS_CHECK_FIELDS = {
    "total_amount_paid",
    "total_approved_amount",
    "total_requested_amount",
    "tax_amount",
    "total_amount",
    "icd_code",
}


@dataclass
class FieldError:
    field: str
    reason: str
    severity: str  # "missing_required" | "format" | "cross_check" | "schema"
    value: Any = None


@dataclass
class ValidationReport:
    ok: bool
    errors: list[FieldError] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)

    @property
    def has_missing_required(self) -> bool:
        return bool(self.missing_required)

    def summary(self) -> str:
        if not self.errors:
            return "No issues."
        lines = []
        for e in self.errors:
            lines.append(f"- Field `{e.field}` ({e.severity}): {e.reason}")
        return "\n".join(lines)


def validate(
    cleaned: dict[str, Any],
    doc_type: DocumentType,
    raw_text: str = "",
) -> ValidationReport:
    spec = DOC_TYPE_REGISTRY[doc_type]
    errors: list[FieldError] = []
    missing_required: list[str] = []

    # 1. Pydantic schema check
    try:
        spec.pydantic_model(**cleaned)
    except Exception as exc:
        errors.append(
            FieldError(
                field="<schema>",
                reason=f"Pydantic validation failed: {exc}",
                severity="schema",
            )
        )

    # 2. Required-field presence
    for fname in spec.required_fields:
        if cleaned.get(fname) in (None, ""):
            missing_required.append(fname)
            errors.append(
                FieldError(
                    field=fname,
                    reason="Required field is missing.",
                    severity="missing_required",
                )
            )

    # 3. Date format check (defensive — postprocess should already enforce this)
    for fname in ("claimant_date_of_birth", "discharge_date_time",
                  "submission_date_time", "date_of_mc"):
        if fname not in cleaned:
            continue
        v = cleaned[fname]
        if v is None:
            continue
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", str(v)):
            errors.append(
                FieldError(
                    field=fname,
                    reason=f"Expected DD/MM/YYYY, got {v!r}.",
                    severity="format",
                    value=v,
                )
            )

    # 4. Cross-check against raw PDF text where available
    if raw_text:
        text_digits = re.sub(r"\D", "", raw_text)
        for fname in CROSS_CHECK_FIELDS:
            if fname not in cleaned:
                continue
            v = cleaned[fname]
            if v is None:
                continue
            if isinstance(v, int):
                if str(v) not in text_digits:
                    errors.append(
                        FieldError(
                            field=fname,
                            reason=(
                                f"Value {v} not found in document text (digits "
                                "extracted from raw PDF do not contain it)."
                            ),
                            severity="cross_check",
                            value=v,
                        )
                    )
            elif isinstance(v, str):
                if v.lower() not in raw_text.lower():
                    errors.append(
                        FieldError(
                            field=fname,
                            reason=f"Value {v!r} not found in document text.",
                            severity="cross_check",
                            value=v,
                        )
                    )

    return ValidationReport(
        ok=not errors,
        errors=errors,
        missing_required=missing_required,
    )


def build_raw_text_hint(raw_text: str, max_lines: int = 12) -> str:
    """Pick lines from raw_text that look relevant to extraction errors.

    Heuristic: lines containing currency symbols, digits with separators,
    date-like patterns, or labels we care about.
    """
    if not raw_text:
        return ""
    keywords_re = re.compile(
        r"(\$|amount|total|paid|approved|requested|tax|gst|"
        r"date|dob|d\.o\.b|icd|name|address|mc\b)",
        re.IGNORECASE,
    )
    digit_re = re.compile(r"\d{2,}")
    selected: list[str] = []
    for line in raw_text.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        if keywords_re.search(line_s) or digit_re.search(line_s):
            selected.append(line_s)
            if len(selected) >= max_lines:
                break
    return "\n".join(selected)
