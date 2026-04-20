"""Run a single extraction call against Gemini for a given document type.

The orchestrator may call this twice: once with the base prompt, once with a
repair-wrapped prompt if validation fails. This module is intentionally dumb —
it does not know about retry. Retry policy lives in the orchestrator.
"""
from __future__ import annotations

from typing import Any

from PIL import Image

from app.clients.gemini import GeminiClient, get_gemini_client
from app.prompts import EXTRACTION_PROMPTS
from app.schemas import DOC_TYPE_REGISTRY
from app.schemas.base import DocumentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


def extract(
    image: Image.Image,
    doc_type: DocumentType,
    prompt_override: str | None = None,
    gemini: GeminiClient | None = None,
) -> dict[str, Any]:
    spec = DOC_TYPE_REGISTRY[doc_type]
    prompt = prompt_override or EXTRACTION_PROMPTS[doc_type]
    client = gemini or get_gemini_client()

    raw = client.generate_json(
        prompt=prompt,
        image=image,
        response_schema=spec.gemini_schema,
        temperature=0.0,
    )
    logger.info("extract doc_type=%s field_count=%d", doc_type, len(raw))
    return raw
