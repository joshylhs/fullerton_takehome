from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    log_level: str = "INFO"

    max_file_size_mb: int = 20
    max_pdf_pages: int = 10
    pdf_render_dpi: int = 200

    extraction_timeout_seconds: int = 15
    max_extraction_retries: int = 1

    failure_store_dir: str = "failed_extractions"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


settings = Settings()
