from app.prompts.base import build_extraction_prompt

FIELD_DESCRIPTIONS = """\
- claimant_name: Patient's full name as it appears on the letter.
- provider_name: Name of the referring provider, clinic, or lab.
- signature_presence: true if a handwritten cursive signature is visible, else false.
- total_amount_paid: Amount the claimant has paid (digit string, no separators).
- total_approved_amount: Amount the insurer/payer has approved (digit string).
- total_requested_amount: Amount being requested from the insurer (digit string)."""

EXTRACTION_PROMPT = build_extraction_prompt(
    doc_type_label="referral letter",
    field_descriptions=FIELD_DESCRIPTIONS,
)
