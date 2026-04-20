from unittest.mock import MagicMock

import pytest

from app.pipeline.classify import (
    UnsupportedDocumentTypeError,
    _classify_by_keywords,
    classify,
)
from app.schemas.base import DocumentType


def test_keyword_classify_referral():
    text = "Dear Doctor,\nKindly see this patient for further management. Referral letter."
    result = _classify_by_keywords(text)
    assert result is not None
    doc_type, score = result
    assert doc_type == DocumentType.REFERRAL_LETTER
    assert score >= 2


def test_keyword_classify_receipt():
    text = "TAX INVOICE\nSubtotal: $100\nGST: $7\nTotal Amount: $107"
    result = _classify_by_keywords(text)
    assert result is not None
    assert result[0] == DocumentType.RECEIPT


def test_keyword_classify_mc():
    text = "Medical Certificate\nThis is to certify... 2 days of medical leave."
    result = _classify_by_keywords(text)
    assert result is not None
    assert result[0] == DocumentType.MEDICAL_CERTIFICATE


def test_keyword_classify_inconclusive_returns_none():
    text = "Hello world. This document has no relevant keywords at all."
    assert _classify_by_keywords(text) is None


def test_classify_falls_back_to_llm_when_no_text(blank_image):
    fake_gemini = MagicMock()
    fake_gemini.generate_text.return_value = "receipt"
    result = classify(blank_image, raw_text="", gemini=fake_gemini)
    assert result.document_type == DocumentType.RECEIPT
    assert result.method == "llm"


def test_classify_unsupported_raises(blank_image):
    fake_gemini = MagicMock()
    fake_gemini.generate_text.return_value = "unknown"
    with pytest.raises(UnsupportedDocumentTypeError):
        classify(blank_image, raw_text="", gemini=fake_gemini)


def test_classify_garbage_label_raises(blank_image):
    fake_gemini = MagicMock()
    fake_gemini.generate_text.return_value = "lorem ipsum"
    with pytest.raises(UnsupportedDocumentTypeError):
        classify(blank_image, raw_text="", gemini=fake_gemini)
