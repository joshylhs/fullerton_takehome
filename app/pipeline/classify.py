"""Classify a document into one of the supported types.

Two-stage strategy:
1. Keyword rules over the raw PDF text (free, instant). Requires a confident,
   unambiguous match — score >= MIN_RULE_SCORE and a clear winner.
2. Gemini vision fallback when rules are inconclusive or text is unavailable
   (e.g. image upload, scanned PDF).

If Gemini returns 'unknown', we raise UnsupportedDocumentTypeError, which the
API layer maps to a 422 response.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image

from app.clients.gemini import GeminiClient, get_gemini_client
from app.prompts.base import CLASSIFY_PROMPT
from app.schemas.base import DocumentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class UnsupportedDocumentTypeError(Exception):
    pass


# Keyword rules — case-insensitive substring matches. Each match adds 1 to the
# score for that doc type. Tuned conservatively: ambiguous documents fall
# through to the LLM.
KEYWORD_RULES: dict[DocumentType, list[str]] = {
    DocumentType.REFERRAL_LETTER: [
        "referral",
        "refer to",
        "referring physician",
        "dear doctor",
        "kindly see",
        "for further management",
    ],
    DocumentType.MEDICAL_CERTIFICATE: [
        "medical certificate",
        "medical leave",
        "unfit for duty",
        "unfit for work",
        "mc no",
        "this is to certify",
        "days of medical leave",
    ],
    DocumentType.RECEIPT: [
        "receipt",
        "tax invoice",
        "invoice no",
        "subtotal",
        "gst",
        "amount paid",
        "payment received",
        "total amount",
    ],
}


MIN_RULE_SCORE = 2  # need at least 2 keyword hits to trust rules


@dataclass
class ClassificationResult:
    document_type: DocumentType
    method: str  # "keyword" | "llm"
    score: int  # rule score (0 if llm)


def classify(
    image: Image.Image,
    raw_text: str,
    gemini: GeminiClient | None = None,
) -> ClassificationResult:
    if raw_text:
        rule_result = _classify_by_keywords(raw_text)
        if rule_result is not None:
            doc_type, score = rule_result
            logger.info("classify method=keyword type=%s score=%d", doc_type, score)
            return ClassificationResult(doc_type, "keyword", score)

    client = gemini or get_gemini_client()
    label = client.generate_text(CLASSIFY_PROMPT, image).strip().lower()
    label = re.sub(r"[^a-z_]", "", label)  # strip punctuation/quotes/etc.

    logger.info("classify method=llm raw_label=%r", label)

    if label == "unknown" or not label:
        raise UnsupportedDocumentTypeError(label or "empty")
    try:
        doc_type = DocumentType(label)
    except ValueError as exc:
        raise UnsupportedDocumentTypeError(label) from exc

    return ClassificationResult(doc_type, "llm", 0)


def _classify_by_keywords(raw_text: str) -> tuple[DocumentType, int] | None:
    """Return (doc_type, score) only if there is a confident, unambiguous winner."""
    text = raw_text.lower()
    scores: dict[DocumentType, int] = {}
    for doc_type, keywords in KEYWORD_RULES.items():
        scores[doc_type] = sum(1 for kw in keywords if kw in text)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_type, top_score = ranked[0]
    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score < MIN_RULE_SCORE:
        return None
    if top_score == runner_up_score:
        return None  # tied -> ambiguous, fall through to LLM
    return top_type, top_score
