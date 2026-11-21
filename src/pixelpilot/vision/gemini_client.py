from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from pixelpilot.vision.parsing import parse_json_model

ModelT = TypeVar("ModelT", bound=BaseModel)
Sleeper = Callable[[float], Awaitable[None]]
RateWaiter = Callable[[], Awaitable[None]]


class RequestRateLimiter:
    def __init__(self, requests_per_minute: float):
        self.interval = 60 / requests_per_minute
        self._lock = asyncio.Lock()
        self._next_request = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._next_request - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_request = time.monotonic() + self.interval


_RATE_LIMITER = RequestRateLimiter(5)


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout: float = 60.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleeper: Sleeper = asyncio.sleep,
        rate_waiter: RateWaiter = _RATE_LIMITER.wait,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport
        self.sleeper = sleeper
        self.rate_waiter = rate_waiter
        self.last_status_code: int | None = None

    async def complete(
        self, prompt: str, image_bytes: bytes, response_model: type[ModelT]
    ) -> ModelT:
        if not self.api_key:
            raise ValueError("PP_GEMINI_API_KEY is not configured")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": 256,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        return await self._execute_request(payload, response_model)

    async def complete_text(self, prompt: str, response_model: type[ModelT]) -> ModelT:
        if not self.api_key:
            raise ValueError("PP_GEMINI_API_KEY is not configured")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": 1024,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        return await self._execute_request(payload, response_model)

    async def _execute_request(
        self, payload: Mapping[str, Any], response_model: type[ModelT]
    ) -> ModelT:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            for attempt in range(self.max_retries + 1):
                await self.rate_waiter()
                try:
                    response = await client.post(
                        url,
                        headers={"x-goog-api-key": self.api_key},
                        json=payload,
                    )
                except httpx.TransportError:
                    if attempt == self.max_retries:
                        raise
                    await self.sleeper(float(2**attempt))
                    continue
                self.last_status_code = response.status_code
                if response.status_code not in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                    return parse_json_model(_response_text(response), response_model)
                if attempt == self.max_retries:
                    response.raise_for_status()
                await self.sleeper(_retry_delay(response, attempt))
        raise RuntimeError("Gemini request loop ended unexpectedly")

    async def probe(self) -> int:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Reply OK"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
        }
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=payload,
            )
        return response.status_code


def _response_text(response: httpx.Response) -> str:
    envelope = response.json()
    try:
        candidate = envelope["candidates"][0]
        parts = candidate["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini response did not contain candidate text") from exc
    for part in reversed(parts):
        if not isinstance(part, dict) or part.get("thought") is True:
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            return text
    finish_reason = candidate.get("finishReason", "unknown")
    raise ValueError(f"Gemini candidate text was empty (finishReason={finish_reason})")


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after is not None:
        try:
            return min(5.0, max(0.0, float(retry_after)))
        except ValueError:
            pass
    try:
        data = response.json()
        for detail in data.get("error", {}).get("details", []):
            delay_str = detail.get("retryDelay")
            if isinstance(delay_str, str) and delay_str.endswith("s"):
                return min(5.0, max(0.0, float(delay_str[:-1])))
    except Exception:
        pass
    return float(min(5.0, 2**attempt))
