"""Persist extractions that failed validation for human review.

Demo implementation: writes JSON record + (for `failed` status) original
document bytes to a local directory. In production this would be replaced
with S3 + a database table + a queue message — the public interface stays
the same.

PHI/PDPA note: stored documents and records contain personal data. Production
deployments must apply encryption-at-rest, access controls, audit logging on
reads, and a retention policy. This demo store has none of those.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

FailureStatus = Literal["recovered_on_retry", "degraded", "failed"]


class FailureStore:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.failure_store_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        status: FailureStatus,
        doc_type: str,
        file_hash: str,
        attempts: list[dict[str, Any]],
        missing_required: list[str],
        original_bytes: bytes | None = None,
        original_extension: str = "bin",
    ) -> str:
        review_id = str(uuid4())
        ts = datetime.now(timezone.utc).isoformat().replace(":", "-")
        record = {
            "id": review_id,
            "timestamp": ts,
            "document_type": doc_type,
            "file_hash": file_hash,
            "final_status": status,
            "attempts": attempts,
            "missing_required_fields": missing_required,
            "reviewed": False,
            "reviewer_notes": None,
            "corrected_output": None,
        }
        record_path = self.base_dir / f"{ts}_{review_id}.json"
        record_path.write_text(json.dumps(record, indent=2, default=str))

        if status == "failed" and original_bytes is not None:
            doc_path = self.base_dir / f"{ts}_{review_id}.{original_extension}"
            doc_path.write_bytes(original_bytes)
            logger.warning(
                "Extraction FAILED, queued for review id=%s missing=%s",
                review_id,
                missing_required,
            )
        elif status == "degraded":
            logger.info(
                "Extraction degraded id=%s (no required fields missing)", review_id
            )
        else:
            logger.info("Extraction recovered on retry id=%s", review_id)

        return review_id


_singleton: FailureStore | None = None


def get_failure_store() -> FailureStore:
    global _singleton
    if _singleton is None:
        _singleton = FailureStore()
    return _singleton
