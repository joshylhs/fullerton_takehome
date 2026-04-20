from dataclasses import dataclass
from typing import Type

from pydantic import BaseModel

from app.schemas.base import DocumentType
from app.schemas.medical_certificate import (
    MEDICAL_CERTIFICATE_GEMINI_SCHEMA,
    MEDICAL_CERTIFICATE_REQUIRED_FIELDS,
    MedicalCertificateFields,
)
from app.schemas.receipt import (
    RECEIPT_GEMINI_SCHEMA,
    RECEIPT_REQUIRED_FIELDS,
    ReceiptFields,
)
from app.schemas.referral_letter import (
    REFERRAL_LETTER_GEMINI_SCHEMA,
    REFERRAL_LETTER_REQUIRED_FIELDS,
    ReferralLetterFields,
)


@dataclass(frozen=True)
class DocumentTypeSpec:
    doc_type: DocumentType
    pydantic_model: Type[BaseModel]
    gemini_schema: dict
    required_fields: list[str]


DOC_TYPE_REGISTRY: dict[DocumentType, DocumentTypeSpec] = {
    DocumentType.REFERRAL_LETTER: DocumentTypeSpec(
        doc_type=DocumentType.REFERRAL_LETTER,
        pydantic_model=ReferralLetterFields,
        gemini_schema=REFERRAL_LETTER_GEMINI_SCHEMA,
        required_fields=REFERRAL_LETTER_REQUIRED_FIELDS,
    ),
    DocumentType.MEDICAL_CERTIFICATE: DocumentTypeSpec(
        doc_type=DocumentType.MEDICAL_CERTIFICATE,
        pydantic_model=MedicalCertificateFields,
        gemini_schema=MEDICAL_CERTIFICATE_GEMINI_SCHEMA,
        required_fields=MEDICAL_CERTIFICATE_REQUIRED_FIELDS,
    ),
    DocumentType.RECEIPT: DocumentTypeSpec(
        doc_type=DocumentType.RECEIPT,
        pydantic_model=ReceiptFields,
        gemini_schema=RECEIPT_GEMINI_SCHEMA,
        required_fields=RECEIPT_REQUIRED_FIELDS,
    ),
}
