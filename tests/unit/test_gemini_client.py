from __future__ import annotations

import httpx
import pytest

from pixelpilot.models import GeminiGroundingResult
from pixelpilot.vision.gemini_client import GeminiClient
from pixelpilot.vision.parsing import VisionParseError


@pytest.mark.asyncio
async def test_gemini_429_huge_retry_delay_is_capped_at_5s() -> None:
    delays: list[float] = []
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "3600"},
                json={"error": {"details": [{"retryDelay": "9999s"}]}},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"box_2d":[10,20,30,40],'
                                    '"confidence":0.9,"description":"btn"}'
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

    client = GeminiClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        sleeper=sleep,
        rate_waiter=lambda: sleep(0),
    )
    result = await client.complete("find button", b"image", GeminiGroundingResult)
    assert result.box_2d == (10, 20, 30, 40)
    assert attempts == 2
    # Delays include rate_waiter(0) calls, find the retry sleep delay
    retry_delays = [d for d in delays if d > 0]
    assert retry_delays == [5.0]  # Capped at 5s despite 3600s / 9999s


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", (500, 503))
async def test_gemini_500_503_retries_then_fails_with_clear_error(status_code: int) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            status_code,
            text="server error from host with key secret-test-key-xyz",
            request=request,
        )

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = GeminiClient(
        "secret-test-key-xyz",
        max_retries=2,
        transport=httpx.MockTransport(handler),
        sleeper=sleep,
        rate_waiter=lambda: sleep(0),
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.complete("find button", b"image", GeminiGroundingResult)

    assert attempts == 3  # initial + 2 retries
    err_msg = str(exc_info.value)
    assert str(status_code) in err_msg
    assert "secret-test-key-xyz" not in err_msg
    assert "[REDACTED]" in err_msg or "secret-test-key-xyz" not in err_msg


@pytest.mark.asyncio
async def test_gemini_handles_code_fenced_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "```json\n"
                                    '{"box_2d":[50,60,70,80],"confidence":0.95,"description":"cart"}\n'
                                    "```"
                                }
                            ]
                        }
                    }
                ]
            },
            request=request,
        )

    client = GeminiClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        rate_waiter=lambda: asyncio_noop(),
    )
    result = await client.complete("find cart", b"image", GeminiGroundingResult)
    assert result.box_2d == (50, 60, 70, 80)
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_gemini_malformed_json_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"box_2d": [10, 20, incomplete'}]}}]
            },
            request=request,
        )

    client = GeminiClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        rate_waiter=lambda: asyncio_noop(),
    )
    with pytest.raises(VisionParseError) as exc_info:
        await client.complete("find cart", b"image", GeminiGroundingResult)
    assert "invalid JSON" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response_payload", "expected_err"),
    [
        ({"candidates": []}, "did not contain candidate text"),
        (
            {"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]},
            "candidate text was empty (finishReason=SAFETY)",
        ),
        (
            {
                "candidates": [
                    {
                        "content": {"parts": [{"thought": True, "text": "hmm"}]},
                        "finishReason": "STOP",
                    }
                ]
            },
            "candidate text was empty (finishReason=STOP)",
        ),
    ],
)
async def test_gemini_empty_response_gives_readable_error(
    response_payload: dict[str, object], expected_err: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload, request=request)

    client = GeminiClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        rate_waiter=lambda: asyncio_noop(),
    )
    with pytest.raises(ValueError) as exc_info:
        await client.complete("find cart", b"image", GeminiGroundingResult)
    assert expected_err in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_error_message_includes_status_and_never_key() -> None:
    secret_key = "my-super-secret-gemini-key-12345"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"code": 400, "message": f"API key {secret_key} is not valid"}},
            request=request,
        )

    client = GeminiClient(
        secret_key,
        transport=httpx.MockTransport(handler),
        rate_waiter=lambda: asyncio_noop(),
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.complete("find button", b"image", GeminiGroundingResult)

    err_text = str(exc_info.value)
    assert "400" in err_text
    assert secret_key not in err_text
    assert "[REDACTED]" in err_text


async def asyncio_noop() -> None:
    pass
