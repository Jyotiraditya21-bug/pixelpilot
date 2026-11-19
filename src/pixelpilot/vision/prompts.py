from __future__ import annotations


def grounding_prompt(intent: str, dom_context: str) -> str:
    return f"""Locate the single visible UI element that best satisfies this intent:
{intent}

DOM context:
{dom_context[:8000]}

Return JSON only with this schema:
{{"bbox":{{"x":0,"y":0,"width":0,"height":0}},"confidence":0.0,"description":"..."}}
Coordinates must be absolute pixels in the supplied resized image, not normalized coordinates."""


def verification_prompt(expectation: str) -> str:
    return f"""Decide whether this screenshot visually proves the expectation:
{expectation}

Return JSON only:
{{"passed":false,"confidence":0.0,"evidence":"visible evidence"}}"""
