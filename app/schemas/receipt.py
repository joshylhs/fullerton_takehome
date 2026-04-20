from pydantic import BaseModel


class ReceiptFields(BaseModel):
    claimant_name: str | None = None
    claimant_address: str | None = None
    claimant_date_of_birth: str | None = None
    provider_name: str | None = None
    tax_amount: int | None = None
    total_amount: int | None = None


RECEIPT_REQUIRED_FIELDS: list[str] = [
    "provider_name",
    "total_amount",
]


RECEIPT_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "claimant_name": {"type": "string", "nullable": True},
        "claimant_address": {"type": "string", "nullable": True},
        "claimant_date_of_birth": {"type": "string", "nullable": True},
        "provider_name": {"type": "string", "nullable": True},
        "tax_amount": {"type": "string", "nullable": True},
        "total_amount": {"type": "string", "nullable": True},
    },
    "required": [],
}
