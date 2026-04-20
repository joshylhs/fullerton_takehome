from app.prompts.base import build_extraction_prompt

FIELD_DESCRIPTIONS = """\
- claimant_name: Full name of the claimant / patient.
- claimant_address: Full mailing address of the claimant if shown.
- claimant_date_of_birth: Patient's date of birth (DD/MM/YYYY).
- diagnosis_name: Free-text diagnosis exactly as written.
- discharge_date_time: Date of discharge (DD/MM/YYYY).
- icd_code: ICD-10 code, e.g. "J06.9". Return the code only, no description.
- provider_name: Issuing clinic or hospital name.
- submission_date_time: Admission date (DD/MM/YYYY).
- date_of_mc: The date the MC was issued (DD/MM/YYYY).
- mc_days: Number of days of medical leave granted (integer as digit string)."""

EXTRACTION_PROMPT = build_extraction_prompt(
    doc_type_label="medical certificate",
    field_descriptions=FIELD_DESCRIPTIONS,
)
