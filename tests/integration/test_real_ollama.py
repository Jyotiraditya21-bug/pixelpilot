import io

import pytest
from PIL import Image

from pixelpilot.models import GroundingResult
from pixelpilot.vision.ollama_client import OllamaClient
from pixelpilot.vision.prompts import grounding_prompt


@pytest.mark.vlm
async def test_real_ollama_grounding() -> None:
    image = Image.new("RGB", (320, 200), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    result = await OllamaClient().complete(
        grounding_prompt("the blank page", "blank image"), buffer.getvalue(), GroundingResult
    )
    assert 0 <= result.confidence <= 1
