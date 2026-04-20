"""Thin wrapper around the Google Generative AI SDK.

Centralises:
- API key configuration
- Model instantiation
- JSON-structured-output calls with timeout and basic retry on transient errors
- Logging of token usage

Pipeline code should never import google.generativeai directly.
"""
from __future__ import annotations

import json
import time
from typing import Any

import google.generativeai as genai
from PIL import Image

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TRANSIENT_ERROR_SUBSTRINGS = ("429", "500", "503", "504", "deadline", "unavailable")


class GeminiClientError(Exception):
    pass


class GeminiClient:
    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        key = api_key or settings.gemini_api_key
        if not key:
            raise GeminiClientError("GEMINI_API_KEY is not set")
        genai.configure(api_key=key)
        self.model_name = model_name or settings.gemini_model
        self._model = genai.GenerativeModel(self.model_name)

    def generate_json(
        self,
        prompt: str,
        image: Image.Image,
        response_schema: dict,
        temperature: float = 0.0,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        """Call Gemini with image + prompt, return parsed JSON.

        Uses Gemini's response_mime_type=application/json + response_schema to
        guarantee well-formed JSON matching the schema. Retries up to
        max_attempts on transient errors (rate limits, server errors).
        """
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": temperature,
        }

        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = self._model.generate_content(
                    [prompt, image],
                    generation_config=generation_config,
                    request_options={"timeout": settings.extraction_timeout_seconds},
                )
                self._log_usage(response)
                return json.loads(response.text)
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                is_transient = any(s in msg for s in _TRANSIENT_ERROR_SUBSTRINGS)
                if attempt < max_attempts and is_transient:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "Gemini transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt,
                        max_attempts,
                        backoff,
                        exc,
                    )
                    time.sleep(backoff)
                    continue
                break

        raise GeminiClientError(f"Gemini call failed: {last_exc}") from last_exc

    def generate_text(
        self,
        prompt: str,
        image: Image.Image,
        temperature: float = 0.0,
    ) -> str:
        """Plain text response (used by the classifier fallback)."""
        try:
            response = self._model.generate_content(
                [prompt, image],
                generation_config={"temperature": temperature},
                request_options={"timeout": settings.extraction_timeout_seconds},
            )
            self._log_usage(response)
            return (response.text or "").strip()
        except Exception as exc:
            raise GeminiClientError(f"Gemini text call failed: {exc}") from exc

    def _log_usage(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            logger.info(
                "gemini_usage prompt_tokens=%s candidates_tokens=%s total=%s",
                getattr(usage, "prompt_token_count", "?"),
                getattr(usage, "candidates_token_count", "?"),
                getattr(usage, "total_token_count", "?"),
            )


_singleton: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _singleton
    if _singleton is None:
        _singleton = GeminiClient()
    return _singleton
