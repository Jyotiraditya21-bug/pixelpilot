from __future__ import annotations


def grounding_prompt(intent: str, dom_context: str) -> str:
    return f"""Locate the single visible UI element that best satisfies this intent:
{intent}

DOM context:
{dom_context[:8000]}

Return JSON only with this schema:
{{"box_2d":[ymin,xmin,ymax,xmax],"confidence":0.0,"description":"..."}}
box_2d coordinates must be integers normalized to 0-1000 in the exact order shown."""


def verification_prompt(expectation: str) -> str:
    return f"""Decide whether this screenshot visually proves the expectation:
{expectation}

Return JSON only:
{{"passed":false,"confidence":0.0,"evidence":"visible evidence"}}"""


def planner_prompt(story_text: str, base_url: str) -> str:
    return f"""Generate an executable browser automation plan for this story against the base URL:
Base URL: {base_url}

Story:
{story_text}

Return JSON only adhering strictly to this schema:
{{
  "story": "story title",
  "expectation": "expected success outcome",
  "steps": [
    {{
      "number": 1,
      "action": {{
        "kind": "navigate",
        "intent": "open page",
        "value": "{base_url}"
      }}
    }}
  ]
}}"""
