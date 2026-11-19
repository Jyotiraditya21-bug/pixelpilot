from __future__ import annotations

import base64
from typing import TypeVar

import httpx
from pydantic import BaseModel

from pixelpilot.vision.parsing import parse_json_model

ModelT = TypeVar("ModelT", bound=BaseModel)


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5vl:3b",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def complete(
        self, prompt: str, image_bytes: bytes, response_model: type[ModelT]
    ) -> ModelT:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            envelope = response.json()
        content = envelope.get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response did not contain message.content")
        return parse_json_model(content, response_model)
