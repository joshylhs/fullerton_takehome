from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    REFERRAL_LETTER = "referral_letter"
    MEDICAL_CERTIFICATE = "medical_certificate"
    RECEIPT = "receipt"


class ExtractionResult(BaseModel):
    document_type: DocumentType
    total_time: float
    finalJson: dict[str, Any]
    attempts: int = 1
    low_confidence: bool = False
    failed_fields: list[str] = Field(default_factory=list)
    review_id: str | None = None
    stage_timings: dict[str, float] = Field(default_factory=dict)


class SuccessResponse(BaseModel):
    message: str
    result: ExtractionResult


class ErrorResponse(BaseModel):
    error: str
