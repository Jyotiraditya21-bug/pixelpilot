import io

import pytest
from PIL import Image

from pixelpilot.config import settings
from pixelpilot.models import GeminiGroundingResult
from pixelpilot.vision.gemini_client import GeminiClient
from pixelpilot.vision.prompts import grounding_prompt


@pytest.mark.vlm
async def test_real_gemini_grounding() -> None:
    image = Image.new("RGB", (320, 200), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    result = await GeminiClient(
        settings.gemini_api_key.get_secret_value(), settings.vlm_model
    ).complete(
        grounding_prompt("the blank page", "blank image"),
        buffer.getvalue(),
        GeminiGroundingResult,
    )
    assert 0 <= result.confidence <= 1
