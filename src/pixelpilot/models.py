from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBox(StrictModel):
    x: float
    y: float
    width: float = Field(ge=0)
    height: float = Field(ge=0)

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2


class ElementSnapshot(StrictModel):
    tag: str
    role: str | None = None
    name: str = ""
    text: str = ""
    bbox: BBox


class PageSnapshot(StrictModel):
    url: str
    title: str
    text: str
    elements: tuple[ElementSnapshot, ...]
    viewport_width: int
    viewport_height: int


class ActionKind(StrEnum):
    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"


class ActionRequest(StrictModel):
    kind: ActionKind
    intent: str
    value: str | None = None
    role: str | None = None
    name: str | None = None
    text: str | None = None
    bbox: BBox | None = None
    locator: str | None = None


class ActionResult(StrictModel):
    success: bool
    detail: str


class Screenshot(StrictModel):
    path: Path
    width: int
    height: int


class GroundingResult(StrictModel):
    bbox: BBox
    confidence: float = Field(ge=0, le=1)
    description: str
    http_status: int | None = None


class GeminiGroundingResult(StrictModel):
    box_2d: tuple[float, float, float, float]
    confidence: float = Field(ge=0, le=1)
    description: str


class VisualVerification(StrictModel):
    passed: bool
    confidence: float = Field(ge=0, le=1)
    evidence: str


class GroundingTier(StrEnum):
    CACHE = "cached_locator"
    ROLE_NAME = "role_name"
    DOM_TEXT = "dom_text"
    VLM = "vlm_bbox"


class PlanStep(StrictModel):
    number: int = Field(ge=1)
    action: ActionRequest


class Plan(StrictModel):
    story: str
    expectation: str
    steps: tuple[PlanStep, ...]


class GroundedAction(StrictModel):
    action: ActionRequest
    tier: GroundingTier
    confidence: float = Field(ge=0, le=1)
    healed: bool = False
    vlm_ms: float = 0.0
    http_status: int | None = None


class VerificationResult(StrictModel):
    passed: bool
    evidence: str
    used_vision: bool = False
    confidence: float = Field(ge=0, le=1)


class StepRecord(StrictModel):
    number: int
    intent: str
    success: bool
    tier: GroundingTier | None = None
    healed: bool = False
    confidence: float = 0.0
    vlm_ms: float = 0.0
    http_status: int | None = None
    detail: str = ""
    screenshot: Path | None = None
    bbox: BBox | None = None


class RunRecord(StrictModel):
    run_id: str
    story: str
    trace_id: str = ""
    passed: bool
    evidence: str
    steps: tuple[StepRecord, ...]
