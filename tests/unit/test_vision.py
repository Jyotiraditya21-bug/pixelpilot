import io

import httpx
import pytest
from PIL import Image

from pixelpilot.models import BBox, GeminiGroundingResult, GroundingResult
from pixelpilot.vision.coords import box_2d_to_viewport, resize_for_vlm
from pixelpilot.vision.gemini_client import GeminiClient
from pixelpilot.vision.parsing import VisionParseError, parse_json_model


def test_parser_accepts_json_fence_and_rejects_prose() -> None:
    result = parse_json_model(
        '```json\n{"bbox":{"x":10,"y":20,"width":30,"height":40},'
        '"confidence":0.9,"description":"buy"}\n```',
        GroundingResult,
    )
    assert result.bbox.center == (25, 40)
    with pytest.raises(VisionParseError):
        parse_json_model("Here is the result: {}", GroundingResult)


def test_resize_and_absolute_coordinate_conversion() -> None:
    source = Image.new("RGB", (2560, 1280), "white")
    buffer = io.BytesIO()
    source.save(buffer, "PNG")
    encoded, transform = resize_for_vlm(buffer.getvalue())
    assert Image.open(io.BytesIO(encoded)).size == (1280, 640)
    assert transform.to_source(BBox(x=100, y=50, width=200, height=100)) == BBox(
        x=200, y=100, width=400, height=200
    )


def test_parser_rejects_extra_fields() -> None:
    with pytest.raises(VisionParseError):
        parse_json_model(
            '{"bbox":{"x":0,"y":0,"width":1,"height":1},'
            '"confidence":1,"description":"x","extra":true}',
            GroundingResult,
        )


def test_gemini_box_2d_to_viewport_pixels() -> None:
    assert box_2d_to_viewport((100, 250, 600, 750), 1280, 900) == BBox(
        x=320, y=90, width=640, height=450
    )


@pytest.mark.asyncio
async def test_gemini_json_request_and_429_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["x-goog-api-key"] == "secret"
        assert b'"temperature":0' in request.content
        if attempts == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, request=request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"box_2d":[100,200,300,400],'
                                    '"confidence":0.8,"description":"button"}'
                                }
                            ]
                        }
                    }
                ]
            },
            request=request,
        )

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = GeminiClient("secret", transport=httpx.MockTransport(handler), sleeper=sleep)
    result = await client.complete("locate", b"jpeg", GeminiGroundingResult)
    assert result.box_2d == (100, 200, 300, 400)
    assert attempts == 2
    assert delays == [0]


@pytest.mark.asyncio
async def test_gemini_probe_is_one_tiny_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(403, request=request)

    client = GeminiClient("bad-key", transport=httpx.MockTransport(handler))
    assert await client.probe() == 403
    assert len(requests) == 1
    assert b"inlineData" not in requests[0].content
    assert b'"maxOutputTokens":1' in requests[0].content
