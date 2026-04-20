from app.prompts.base import build_extraction_prompt

FIELD_DESCRIPTIONS = """\
- claimant_name: The customer / patient name on the receipt.
- claimant_address: Billing address shown on the receipt.
- claimant_date_of_birth: Date of birth if printed on the receipt (DD/MM/YYYY).
- provider_name: Name of the issuing clinic, hospital, or pharmacy.
- tax_amount: Tax / GST amount (digit string, separators and decimals stripped).
- total_amount: Final total amount charged (digit string, separators and decimals stripped)."""

EXTRACTION_PROMPT = build_extraction_prompt(
    doc_type_label="receipt",
    field_descriptions=FIELD_DESCRIPTIONS,
)
