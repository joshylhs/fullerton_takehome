from pydantic import BaseModel


class MedicalCertificateFields(BaseModel):
    claimant_name: str | None = None
    claimant_address: str | None = None
    claimant_date_of_birth: str | None = None
    diagnosis_name: str | None = None
    discharge_date_time: str | None = None
    icd_code: str | None = None
    provider_name: str | None = None
    submission_date_time: str | None = None
    date_of_mc: str | None = None
    mc_days: int | None = None


MEDICAL_CERTIFICATE_REQUIRED_FIELDS: list[str] = [
    "claimant_name",
    "date_of_mc",
    "mc_days",
]


MEDICAL_CERTIFICATE_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "claimant_name": {"type": "string", "nullable": True},
        "claimant_address": {"type": "string", "nullable": True},
        "claimant_date_of_birth": {"type": "string", "nullable": True},
        "diagnosis_name": {"type": "string", "nullable": True},
        "discharge_date_time": {"type": "string", "nullable": True},
        "icd_code": {"type": "string", "nullable": True},
        "provider_name": {"type": "string", "nullable": True},
        "submission_date_time": {"type": "string", "nullable": True},
        "date_of_mc": {"type": "string", "nullable": True},
        "mc_days": {"type": "string", "nullable": True},
    },
    "required": [],
}
