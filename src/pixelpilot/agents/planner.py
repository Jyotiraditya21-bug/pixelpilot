from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from pixelpilot.models import ActionKind, ActionRequest, Plan, PlanStep


class Planner:
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
