import pytest

from app.pipeline.postprocess import (
    filter_provider_name,
    normalize_amount,
    normalize_date,
    normalize_integer,
    postprocess,
)
from app.schemas.base import DocumentType


class TestNormalizeAmount:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("$30,000.00", 3000000),
            ("S$ 1,234.56", 123456),
            ("3000000", 3000000),
            (3000000, 3000000),
            (123.45, 123),
            ("", None),
            ("N/A", None),
            (None, None),
            ("USD 50", 50),
        ],
    )
    def test_amount_normalisation(self, value, expected):
        assert normalize_amount(value) == expected


class TestNormalizeDate:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("12/03/1985", "12/03/1985"),
            ("12-03-1985", "12/03/1985"),
            ("1985-03-12", "12/03/1985"),
            ("12 March 1985", "12/03/1985"),
            ("12 Mar 1985", "12/03/1985"),
            ("not a date", None),
            ("", None),
            (None, None),
            ("32/13/2020", None),  # invalid day/month
        ],
    )
    def test_date_normalisation(self, value, expected):
        assert normalize_date(value) == expected


class TestProviderFilter:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("Fullerton Health Clinic", None),
            ("FULLERTONHEALTH", None),       # no whitespace
            ("Fullerton  Health", None),     # extra whitespace
            ("fullerton health pte ltd", None),
            ("Raffles Medical", "Raffles Medical"),
            ("", None),
            (None, None),
            ("  Mount Elizabeth  ", "Mount Elizabeth"),
        ],
    )
    def test_fullerton_stripped(self, value, expected):
        assert filter_provider_name(value) == expected


class TestNormalizeInteger:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("3", 3),
            ("3 days", 3),
            (3, 3),
            (3.7, 3),
            ("none", None),
            (None, None),
            (True, None),
        ],
    )
    def test_integer_normalisation(self, value, expected):
        assert normalize_integer(value) == expected


class TestPostprocessReceipt:
    def test_basic_receipt(self):
        raw = {
            "claimant_name": " Jane Doe ",
            "provider_name": "Raffles Medical",
            "tax_amount": "$70.00",
            "total_amount": "$1,070.00",
        }
        out = postprocess(raw, DocumentType.RECEIPT)
        assert out["claimant_name"] == "Jane Doe"
        assert out["provider_name"] == "Raffles Medical"
        assert out["tax_amount"] == 7000
        assert out["total_amount"] == 107000
        # missing fields populated as None
        assert out["claimant_address"] is None

    def test_fullerton_provider_dropped(self):
        raw = {"provider_name": "Fullerton Health Singapore", "total_amount": "100"}
        out = postprocess(raw, DocumentType.RECEIPT)
        assert out["provider_name"] is None
