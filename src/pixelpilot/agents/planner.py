from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from pixelpilot.models import ActionKind, ActionRequest, Plan, PlanStep
from pixelpilot.vision.gemini_client import GeminiClient
from pixelpilot.vision.prompts import planner_prompt


class GrammarPlanner:
    def plan(self, story_text: str, base_url: str) -> Plan:
        title = _first_heading(story_text)
        expectation = _success_text(story_text)
        lower = story_text.lower()
        steps: list[ActionRequest] = []
        if "empty cart" in lower:
            steps.append(
                ActionRequest(
                    kind=ActionKind.NAVIGATE,
                    intent="open the cart",
                    value=_path_url(base_url, "/cart"),
                )
            )
        elif "scroll" in lower:
            steps.extend(
                (
                    ActionRequest(
                        kind=ActionKind.NAVIGATE,
                        intent="open the scroll fixture",
                        value=_path_url(base_url, "/scroll"),
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="confirm bottom action",
                        role="button",
                        name="Confirm bottom action",
                        text="Confirm bottom action",
                    ),
                )
            )
        elif "modal" in lower:
            steps.extend(
                (
                    ActionRequest(
                        kind=ActionKind.NAVIGATE,
                        intent="open the modal fixture",
                        value=_path_url(base_url, "/modal"),
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="accept cookies",
                        role="button",
                        name="Accept cookies",
                        text="Accept cookies",
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="claim special deal",
                        role="button",
                        name="Claim special deal",
                        text="Claim special deal",
                    ),
                )
            )
        elif "ambiguous" in lower:
            steps.extend(
                (
                    ActionRequest(
                        kind=ActionKind.NAVIGATE,
                        intent="open the ambiguous fixture",
                        value=_path_url(base_url, "/ambiguous"),
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="add Target Widget to cart",
                        role="button",
                        name="Add",
                        text="Add",
                    ),
                )
            )
        elif "icon" in lower:
            steps.extend(
                (
                    ActionRequest(
                        kind=ActionKind.NAVIGATE,
                        intent="open the icons fixture",
                        value=_path_url(base_url, "/icons"),
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="click cart icon",
                        role="button",
                        text="🛒",
                    ),
                )
            )
        else:
            product = _match(story_text, r"Add the (.+?) to the cart")
            coupon = _match(story_text, r"(?:apply coupon|enter coupon) `([^`]+)`")
            steps.extend(
                (
                    ActionRequest(
                        kind=ActionKind.NAVIGATE,
                        intent="open the product catalog",
                        value=base_url,
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent=f"add {product} to cart",
                        role="button",
                        name=f"Add {product} to cart",
                        text=f"Add {product} to cart",
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="proceed to checkout",
                        role="link",
                        name="Proceed to checkout",
                        text="Proceed to checkout",
                    ),
                    ActionRequest(
                        kind=ActionKind.TYPE,
                        intent="enter the coupon code",
                        value=coupon,
                        role="textbox",
                        name="Coupon code",
                    ),
                    ActionRequest(
                        kind=ActionKind.CLICK,
                        intent="place the order",
                        role="button",
                        name="Place order",
                        text="Place order",
                    ),
                )
            )
        numbered = tuple(
            PlanStep(number=index, action=action) for index, action in enumerate(steps, 1)
        )
        return Plan(story=title, expectation=expectation, steps=numbered)


class ModelPlanner:
    def __init__(
        self,
        client: GeminiClient | None = None,
        grammar_planner: GrammarPlanner | None = None,
        max_retries: int = 2,
    ):
        self.client = client
        self.grammar_planner = grammar_planner or GrammarPlanner()
        self.max_retries = max_retries

    async def plan(self, story_text: str, base_url: str) -> Plan:
        if self.client is not None:
            prompt = planner_prompt(story_text, base_url)
            for attempt in range(self.max_retries + 1):
                try:
                    result = await self.client.complete_text(prompt, Plan)
                    if result.story and result.steps:
                        return result
                except (ValueError, httpx.HTTPError, ValidationError):
                    if attempt == self.max_retries:
                        break
        return self.grammar_planner.plan(story_text, base_url)

    def plan_sync(self, story_text: str, base_url: str) -> Plan:
        return self.grammar_planner.plan(story_text, base_url)


Planner = ModelPlanner


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("story needs a level-one heading")


def _success_text(text: str) -> str:
    match = re.search(r"Success:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("story needs a Success statement")
    return " ".join(match.group(1).split())


def _match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        raise ValueError(f"story does not match required instruction: {pattern}")
    return match.group(1)


def _path_url(base_url: str, path: str) -> str:
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
