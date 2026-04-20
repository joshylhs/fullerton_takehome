"""API-layer tests using FastAPI's TestClient. Pipeline is mocked at the
process_document boundary so we verify HTTP behaviour, not extraction logic."""
import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.pipeline.classify import UnsupportedDocumentTypeError
from app.schemas.base import DocumentType, ExtractionResult


@pytest.fixture
def client():
    return TestClient(app)


def _png_file() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_missing_file_returns_400(client):
    r = client.post("/ocr")
    assert r.status_code == 400
    assert r.json() == {"error": "file_missing"}


def test_invalid_mime_returns_400(client):
    r = client.post(
        "/ocr",
        files={"file": ("doc.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json() == {"error": "file_missing"}


def test_unsupported_doc_type_returns_422(client):
    fake_result = UnsupportedDocumentTypeError("unknown")
    with patch(
        "app.api.routes.process_document", side_effect=fake_result
    ):
        r = client.post(
            "/ocr",
            files={"file": ("x.png", _png_file(), "image/png")},
        )
    assert r.status_code == 422
    assert r.json() == {"error": "unsupported_document_type"}


def test_unhandled_exception_returns_500(client):
    with patch(
        "app.api.routes.process_document", side_effect=RuntimeError("boom")
    ):
        r = client.post(
            "/ocr",
            files={"file": ("x.png", _png_file(), "image/png")},
        )
    assert r.status_code == 500
    assert r.json() == {"error": "internal_server_error"}


def test_success_envelope(client):
    fake_result = ExtractionResult(
        document_type=DocumentType.RECEIPT,
        total_time=1.23,
        finalJson={
            "claimant_name": "Jane Doe",
            "claimant_address": "1 Main St",
            "claimant_date_of_birth": "01/01/1990",
            "provider_name": "Raffles",
            "tax_amount": 7000,
            "total_amount": 107000,
        },
        attempts=1,
    )
    with patch("app.api.routes.process_document", return_value=fake_result):
        r = client.post(
            "/ocr",
            files={"file": ("x.png", _png_file(), "image/png")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "Processing completed."
    assert body["result"]["document_type"] == "receipt"
    assert body["result"]["finalJson"]["total_amount"] == 107000
    assert body["result"]["low_confidence"] is False


def test_low_confidence_message(client):
    fake_result = ExtractionResult(
        document_type=DocumentType.RECEIPT,
        total_time=1.23,
        finalJson={"total_amount": None},
        attempts=2,
        low_confidence=True,
        failed_fields=["total_amount"],
        review_id="abc-123",
    )
    with patch("app.api.routes.process_document", return_value=fake_result):
        r = client.post(
            "/ocr",
            files={"file": ("x.png", _png_file(), "image/png")},
        )
    assert r.status_code == 200
    body = r.json()
    assert "low confidence" in body["message"].lower()
    assert body["result"]["review_id"] == "abc-123"
