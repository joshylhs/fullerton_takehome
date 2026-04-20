from fastapi.responses import JSONResponse


def file_missing() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "file_missing"})


def unsupported_document_type() -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"error": "unsupported_document_type"}
    )


def internal_server_error() -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": "internal_server_error"})
