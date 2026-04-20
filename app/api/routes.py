from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.api import errors
from app.pipeline.classify import UnsupportedDocumentTypeError
from app.pipeline.normalize import (
    SUPPORTED_MIME,
    FileTooLargeError,
    UnsupportedMimeError,
)
from app.pipeline.orchestrator import process_document
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/ocr")
async def ocr_endpoint(file: UploadFile | None = File(default=None)):
    if file is None or not file.filename:
        return errors.file_missing()

    content_type = (file.content_type or "").lower()
    if content_type not in SUPPORTED_MIME:
        return errors.file_missing()

    try:
        file_bytes = await file.read()
    except Exception as exc:
        logger.exception("Failed to read uploaded file: %s", exc)
        return errors.internal_server_error()

    if not file_bytes:
        return errors.file_missing()

    try:
        result = process_document(file_bytes, content_type)
    except (UnsupportedMimeError, FileTooLargeError):
        return errors.file_missing()
    except UnsupportedDocumentTypeError:
        return errors.unsupported_document_type()
    except Exception as exc:
        logger.exception("Unhandled pipeline error: %s", exc)
        return errors.internal_server_error()

    message = (
        "Processing completed."
        if not result.low_confidence
        else "Processing completed with low confidence."
    )
    return JSONResponse(
        status_code=200,
        content={
            "message": message,
            "result": result.model_dump(mode="json"),
        },
    )
