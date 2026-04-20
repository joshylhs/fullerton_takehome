import io
import os

# Ensure tests don't accidentally hit the real Gemini API.
os.environ.setdefault("GEMINI_API_KEY", "test-key")

import pytest
from PIL import Image


@pytest.fixture
def blank_image() -> Image.Image:
    return Image.new("RGB", (200, 200), color="white")


@pytest.fixture
def png_bytes(blank_image: Image.Image) -> bytes:
    buf = io.BytesIO()
    blank_image.save(buf, format="PNG")
    return buf.getvalue()
