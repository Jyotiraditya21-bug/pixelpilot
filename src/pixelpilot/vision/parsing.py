from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class VisionParseError(ValueError):
    """Raised when a VLM response is not one strict JSON document."""


def parse_json_model(content: str, model: type[ModelT]) -> ModelT:
    match = _FENCE.fullmatch(content)
    candidate = match.group(1) if match else content.strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise VisionParseError(f"invalid JSON: {exc.msg}") from exc
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise VisionParseError(f"invalid response schema: {exc}") from exc
