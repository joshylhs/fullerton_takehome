"""Top-level pipeline orchestrator.

Glues stages together and handles the retry policy. The API layer calls
process_document() with raw bytes + content type and gets back an
ExtractionResult ready to be wrapped in a SuccessResponse.

Flow:
  normalise -> classify -> extract -> postprocess -> validate
                                ^                        |
                                |  (1 retry on failure)  |
                                +------------------------+
                                       repair prompt

Final outcome is one of:
  - clean pass            -> ExtractionResult, no failure record
  - recovered on retry    -> ExtractionResult, store as 'recovered_on_retry'
  - degraded after retry  -> ExtractionResult + low_confidence, store as 'degraded'
  - failed after retry    -> ExtractionResult + low_confidence + review_id,
                             store as 'failed' with original bytes
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.config import settings
from app.pipeline import classify as classify_stage
from app.pipeline import extract as extract_stage
from app.pipeline import normalize as normalize_stage
from app.pipeline import postprocess as postprocess_stage
from app.pipeline import validate as validate_stage
from app.prompts import EXTRACTION_PROMPTS
from app.prompts.base import build_repair_prompt
from app.schemas import DOC_TYPE_REGISTRY
from app.schemas.base import DocumentType, ExtractionResult
from app.storage.failure_store import FailureStore, get_failure_store
from app.utils.hashing import sha256_hex
from app.utils.logging import get_logger
from app.utils.timing import StageTimings

logger = get_logger(__name__)


def process_document(
    file_bytes: bytes,
    content_type: str,
    failure_store: FailureStore | None = None,
) -> ExtractionResult:
    """End-to-end pipeline. Raises on unsupported MIME or unsupported doc type;
    otherwise always returns an ExtractionResult (with low_confidence flags
    when relevant)."""
    timings = StageTimings()
    store = failure_store or get_failure_store()

    with timings.measure("normalize"):
        doc = normalize_stage.normalise(file_bytes, content_type)

    with timings.measure("classify"):
        cls_result = classify_stage.classify(doc.image, doc.raw_text)
    doc_type = cls_result.document_type

    attempts_log: list[dict[str, Any]] = []

    # ---- Attempt 1: base prompt
    with timings.measure("extract_attempt_1"):
        raw_1 = extract_stage.extract(doc.image, doc_type)
    cleaned_1 = postprocess_stage.postprocess(raw_1, doc_type)
    report_1 = validate_stage.validate(cleaned_1, doc_type, doc.raw_text)
    attempts_log.append(
        _attempt_record(1, raw_1, cleaned_1, report_1, prompt="base")
    )

    if report_1.ok:
        return _build_success_result(
            doc_type=doc_type,
            cleaned=cleaned_1,
            attempts=1,
            timings=timings,
            low_confidence=False,
            failed_fields=[],
            review_id=None,
        )

    # ---- Attempt 2: repair prompt (only if retries enabled)
    if settings.max_extraction_retries < 1:
        return _finalise_with_failure(
            doc_type=doc_type,
            best_cleaned=cleaned_1,
            best_report=report_1,
            attempts=1,
            attempts_log=attempts_log,
            timings=timings,
            store=store,
            file_bytes=file_bytes,
            content_type=content_type,
        )

    base_prompt = EXTRACTION_PROMPTS[doc_type]
    repair_prompt = build_repair_prompt(
        base_prompt=base_prompt,
        failure_summary=report_1.summary(),
        raw_text_hint=validate_stage.build_raw_text_hint(doc.raw_text),
    )

    with timings.measure("extract_attempt_2"):
        raw_2 = extract_stage.extract(doc.image, doc_type, prompt_override=repair_prompt)
    cleaned_2 = postprocess_stage.postprocess(raw_2, doc_type)
    report_2 = validate_stage.validate(cleaned_2, doc_type, doc.raw_text)
    attempts_log.append(
        _attempt_record(2, raw_2, cleaned_2, report_2, prompt="repair")
    )

    # Pick the better of the two attempts (fewer errors wins)
    if len(report_2.errors) < len(report_1.errors):
        best_cleaned, best_report = cleaned_2, report_2
    else:
        best_cleaned, best_report = cleaned_1, report_1

    if best_report.ok:
        # The retry recovered.
        review_id = store.record(
            status="recovered_on_retry",
            doc_type=doc_type.value,
            file_hash=sha256_hex(file_bytes),
            attempts=attempts_log,
            missing_required=[],
        )
        return _build_success_result(
            doc_type=doc_type,
            cleaned=best_cleaned,
            attempts=2,
            timings=timings,
            low_confidence=False,
            failed_fields=[],
            review_id=review_id,
        )

    return _finalise_with_failure(
        doc_type=doc_type,
        best_cleaned=best_cleaned,
        best_report=best_report,
        attempts=2,
        attempts_log=attempts_log,
        timings=timings,
        store=store,
        file_bytes=file_bytes,
        content_type=content_type,
    )


def _attempt_record(
    n: int,
    raw: dict[str, Any],
    cleaned: dict[str, Any],
    report: validate_stage.ValidationReport,
    prompt: str,
) -> dict[str, Any]:
    return {
        "attempt": n,
        "prompt_kind": prompt,
        "raw": raw,
        "cleaned": cleaned,
        "errors": [asdict(e) for e in report.errors],
        "missing_required": report.missing_required,
    }


def _finalise_with_failure(
    doc_type: DocumentType,
    best_cleaned: dict[str, Any],
    best_report: validate_stage.ValidationReport,
    attempts: int,
    attempts_log: list[dict[str, Any]],
    timings: StageTimings,
    store: FailureStore,
    file_bytes: bytes,
    content_type: str,
) -> ExtractionResult:
    failed_fields = [e.field for e in best_report.errors if e.field != "<schema>"]
    status = "failed" if best_report.has_missing_required else "degraded"
    extension = _extension_for(content_type)

    review_id = store.record(
        status=status,
        doc_type=doc_type.value,
        file_hash=sha256_hex(file_bytes),
        attempts=attempts_log,
        missing_required=best_report.missing_required,
        original_bytes=file_bytes if status == "failed" else None,
        original_extension=extension,
    )

    return _build_success_result(
        doc_type=doc_type,
        cleaned=best_cleaned,
        attempts=attempts,
        timings=timings,
        low_confidence=True,
        failed_fields=sorted(set(failed_fields)),
        review_id=review_id,
    )


def _build_success_result(
    doc_type: DocumentType,
    cleaned: dict[str, Any],
    attempts: int,
    timings: StageTimings,
    low_confidence: bool,
    failed_fields: list[str],
    review_id: str | None,
) -> ExtractionResult:
    spec = DOC_TYPE_REGISTRY[doc_type]
    ordered = {k: cleaned.get(k) for k in spec.pydantic_model.model_fields.keys()}
    return ExtractionResult(
        document_type=doc_type,
        total_time=timings.total,
        finalJson=ordered,
        attempts=attempts,
        low_confidence=low_confidence,
        failed_fields=failed_fields,
        review_id=review_id,
        stage_timings=timings.stages,
    )


def _extension_for(content_type: str) -> str:
    ct = (content_type or "").lower()
    return {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
    }.get(ct, "bin")
