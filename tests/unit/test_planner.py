from __future__ import annotations

import httpx
import pytest

from pixelpilot.agents.planner import GrammarPlanner, ModelPlanner
from pixelpilot.models import ActionKind, Plan
from pixelpilot.vision.gemini_client import GeminiClient


@pytest.mark.asyncio
async def test_model_planner_successful_strict_json() -> None:
    plan_json = """{
      "story": "Custom user story",
      "expectation": "Target action completed",
      "steps": [
        {
          "number": 1,
          "action": {
            "kind": "navigate",
            "intent": "open custom page",
            "value": "http://localhost:8000/custom"
          }
        },
        {
          "number": 2,
          "action": {
            "kind": "click",
            "intent": "click custom button",
            "role": "button",
            "name": "Submit",
            "text": "Submit"
          }
        }
      ]
    }"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": plan_json}]},
                        "finishReason": "STOP",
                    }
                ]
            },
            request=request,
        )

    async def no_rate_wait() -> None:
        return None

    client = GeminiClient(
        "secret-key",
        transport=httpx.MockTransport(handler),
        rate_waiter=no_rate_wait,
    )
    planner = ModelPlanner(client=client, max_retries=2)
    plan = await planner.plan(
        "# Custom user story\n\nDo something.\n\nSuccess: Target action completed.",
        "http://localhost:8000",
    )
    assert isinstance(plan, Plan)
    assert plan.story == "Custom user story"
    assert len(plan.steps) == 2
    assert plan.steps[0].action.kind == ActionKind.NAVIGATE
    assert plan.steps[1].action.kind == ActionKind.CLICK


@pytest.mark.asyncio
async def test_model_planner_retries_and_falls_back_to_grammar() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        # Returns invalid schema / non-JSON
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "not valid json {{"}]},
                        "finishReason": "STOP",
                    }
                ]
            },
            request=request,
        )

    async def no_rate_wait() -> None:
        return None

    client = GeminiClient(
        "secret-key",
        transport=httpx.MockTransport(handler),
        rate_waiter=no_rate_wait,
    )
    planner = ModelPlanner(client=client, max_retries=2)
    # Story matching grammar pattern for scroll fixture
    story = (
        "# Confirm scroll target\n\n"
        "Navigate to the scroll fixture and click the confirm bottom action button.\n\n"
        "Success: the site says “Scroll target reached and confirmed”."
    )
    plan = await planner.plan(story, "http://localhost:8000")
    assert isinstance(plan, Plan)
    assert plan.story == "Confirm scroll target"
    # Initial attempt + 2 retries = 3 attempts total
    assert attempts == 3
    # Succeeded via grammar fallback
    assert len(plan.steps) == 2
    assert plan.steps[0].action.value == "http://localhost:8000/scroll"


def test_grammar_planner_fixtures() -> None:
    grammar = GrammarPlanner()

    # Scroll
    p_scroll = grammar.plan(
        "# Scroll\nScroll down.\nSuccess: done.",
        "http://localhost:8000",
    )
    assert p_scroll.steps[0].action.value == "http://localhost:8000/scroll"

    # Modal
    p_modal = grammar.plan(
        "# Modal\nDismiss modal and claim.\nSuccess: done.",
        "http://localhost:8000",
    )
    assert p_modal.steps[0].action.value == "http://localhost:8000/modal"
    assert len(p_modal.steps) == 3

    # Ambiguous
    p_ambig = grammar.plan(
        "# Ambiguous\nClick ambiguous item.\nSuccess: done.",
        "http://localhost:8000",
    )
    assert p_ambig.steps[0].action.value == "http://localhost:8000/ambiguous"

    # Icons
    p_icons = grammar.plan(
        "# Icons\nClick icon button.\nSuccess: done.",
        "http://localhost:8000",
    )
    assert p_icons.steps[0].action.value == "http://localhost:8000/icons"
