from app.pipeline.validate import build_raw_text_hint, validate
from app.schemas.base import DocumentType


def test_required_field_missing_marks_failed():
    cleaned = {
        "claimant_name": None,
        "provider_name": "Raffles",
        "tax_amount": 0,
        "total_amount": None,  # required
        "claimant_address": None,
        "claimant_date_of_birth": None,
    }
    report = validate(cleaned, DocumentType.RECEIPT)
    assert not report.ok
    assert "total_amount" in report.missing_required
    assert report.has_missing_required


def test_passing_receipt():
    cleaned = {
        "claimant_name": "Jane",
        "claimant_address": "1 Main St",
        "claimant_date_of_birth": "01/01/1990",
        "provider_name": "Raffles",
        "tax_amount": 70,
        "total_amount": 1070,
    }
    report = validate(cleaned, DocumentType.RECEIPT)
    assert report.ok
    assert report.errors == []


def test_cross_check_flags_amount_not_in_text():
    cleaned = {
        "claimant_name": "Jane",
        "provider_name": "Raffles",
        "tax_amount": 70,
        "total_amount": 9999,  # not in raw text
        "claimant_address": None,
        "claimant_date_of_birth": None,
    }
    raw_text = "Subtotal $1000.00\nTax $70.00\nTotal $1070.00"
    report = validate(cleaned, DocumentType.RECEIPT, raw_text=raw_text)
    cross_check_errors = [e for e in report.errors if e.severity == "cross_check"]
    assert any(e.field == "total_amount" for e in cross_check_errors)


def test_bad_date_format_flagged():
    cleaned = {
        "claimant_name": "Jane",
        "claimant_address": None,
        "claimant_date_of_birth": "1990-01-01",  # wrong format
        "provider_name": "Raffles",
        "tax_amount": None,
        "total_amount": 100,
    }
    report = validate(cleaned, DocumentType.RECEIPT)
    format_errors = [e for e in report.errors if e.severity == "format"]
    assert any(e.field == "claimant_date_of_birth" for e in format_errors)


def test_raw_text_hint_picks_relevant_lines():
    raw_text = """\
Patient: Jane Doe
Address: 1 Main St
Subtotal: $1000.00
Tax (GST): $70.00
Total Amount: $1070.00
Random unrelated paragraph with no keywords.
"""
    hint = build_raw_text_hint(raw_text)
    assert "Subtotal" in hint
    assert "Total Amount" in hint
    assert "Random unrelated" not in hint
