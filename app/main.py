from fastapi import FastAPI

from app.api.routes import router
from app.utils.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title="Fullerton OCR Service",
        version="0.1.0",
        description=(
            "Single-endpoint OCR + extraction service for medical documents "
            "(referral letters, medical certificates, receipts)."
        ),
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
