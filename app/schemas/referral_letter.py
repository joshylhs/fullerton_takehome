from pydantic import BaseModel


class ReferralLetterFields(BaseModel):
    """Final validated shape for a referral letter extraction."""

    claimant_name: str | None = None
    provider_name: str | None = None
    signature_presence: bool = False
    total_amount_paid: int | None = None
    total_approved_amount: int | None = None
    total_requested_amount: int | None = None


REFERRAL_LETTER_REQUIRED_FIELDS: list[str] = [
    "claimant_name",
    "provider_name",
    "total_amount_paid",
]


REFERRAL_LETTER_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "claimant_name": {"type": "string", "nullable": True},
        "provider_name": {"type": "string", "nullable": True},
        "signature_presence": {"type": "boolean"},
        "total_amount_paid": {"type": "string", "nullable": True},
        "total_approved_amount": {"type": "string", "nullable": True},
        "total_requested_amount": {"type": "string", "nullable": True},
    },
    "required": ["signature_presence"],
}
