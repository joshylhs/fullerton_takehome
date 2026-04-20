from app.prompts.medical_certificate import EXTRACTION_PROMPT as MC_PROMPT
from app.prompts.receipt import EXTRACTION_PROMPT as RECEIPT_PROMPT
from app.prompts.referral_letter import EXTRACTION_PROMPT as REFERRAL_PROMPT
from app.schemas.base import DocumentType

EXTRACTION_PROMPTS: dict[DocumentType, str] = {
    DocumentType.REFERRAL_LETTER: REFERRAL_PROMPT,
    DocumentType.MEDICAL_CERTIFICATE: MC_PROMPT,
    DocumentType.RECEIPT: RECEIPT_PROMPT,
}
