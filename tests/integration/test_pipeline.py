"""Integration test: full pipeline with Gemini fully mocked."""
from unittest.mock import patch

from app.pipeline.orchestrator import process_document
from app.storage.failure_store import FailureStore


def _png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(buf, format="PNG")
    return buf.getvalue()


class FakeGemini:
    """Minimal stub: returns canned classify + extract responses."""

    def __init__(self, classify_label: str, extract_response: dict):
        self.classify_label = classify_label
        self.extract_response = extract_response
        self.extract_calls = 0

    def generate_text(self, prompt, image, temperature=0.0):
        return self.classify_label

    def generate_json(self, prompt, image, response_schema, temperature=0.0,
                      max_attempts=2):
        self.extract_calls += 1
        return dict(self.extract_response)


def test_pipeline_happy_path_receipt(tmp_path):
    fake = FakeGemini(
        classify_label="receipt",
        extract_response={
            "claimant_name": "Jane Doe",
            "claimant_address": "1 Main St",
            "claimant_date_of_birth": "01/01/1990",
            "provider_name": "Raffles Medical",
            "tax_amount": "$70.00",
            "total_amount": "$1,070.00",
        },
    )
    store = FailureStore(base_dir=str(tmp_path))

    with patch("app.pipeline.classify.get_gemini_client", return_value=fake), \
         patch("app.pipeline.extract.get_gemini_client", return_value=fake):
        result = process_document(_png_bytes(), "image/png", failure_store=store)

    assert result.document_type.value == "receipt"
    assert result.low_confidence is False
    assert result.attempts == 1
    assert result.finalJson["total_amount"] == 107000
    assert result.finalJson["tax_amount"] == 7000
    assert result.finalJson["provider_name"] == "Raffles Medical"
    # No failure record
    assert list(tmp_path.iterdir()) == []


def test_pipeline_retry_recovers(tmp_path):
    """First attempt missing required field; retry returns it."""
    responses = [
        # attempt 1: total_amount missing
        {"claimant_name": "Jane", "provider_name": "Raffles", "total_amount": None},
        # attempt 2: complete
        {
            "claimant_name": "Jane",
            "provider_name": "Raffles",
            "tax_amount": "70",
            "total_amount": "1070",
        },
    ]

    class SeqGemini(FakeGemini):
        def __init__(self):
            super().__init__("receipt", {})
            self.idx = 0

        def generate_json(self, *a, **kw):
            self.extract_calls += 1
            r = responses[self.idx]
            self.idx += 1
            return dict(r)

    fake = SeqGemini()
    store = FailureStore(base_dir=str(tmp_path))

    with patch("app.pipeline.classify.get_gemini_client", return_value=fake), \
         patch("app.pipeline.extract.get_gemini_client", return_value=fake):
        result = process_document(_png_bytes(), "image/png", failure_store=store)

    assert result.attempts == 2
    assert result.low_confidence is False
    assert result.finalJson["total_amount"] == 1070
    # A 'recovered_on_retry' record should be written
    records = list(tmp_path.glob("*.json"))
    assert len(records) == 1


def test_pipeline_failure_writes_review_record(tmp_path):
    """Both attempts miss required field -> failed status, review record + doc saved."""
    fake = FakeGemini(
        classify_label="receipt",
        extract_response={
            "claimant_name": None,
            "provider_name": None,  # required
            "total_amount": None,   # required
        },
    )
    store = FailureStore(base_dir=str(tmp_path))

    with patch("app.pipeline.classify.get_gemini_client", return_value=fake), \
         patch("app.pipeline.extract.get_gemini_client", return_value=fake):
        result = process_document(_png_bytes(), "image/png", failure_store=store)

    assert result.low_confidence is True
    assert result.review_id is not None
    assert "total_amount" in result.failed_fields
    assert "provider_name" in result.failed_fields
    # Original doc + JSON record both written
    pngs = list(tmp_path.glob("*.png"))
    jsons = list(tmp_path.glob("*.json"))
    assert len(pngs) == 1
    assert len(jsons) == 1
