from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from pixelpilot.agents.observer import Observation
from pixelpilot.models import VerificationResult, VisualVerification

VisionVerifier = Callable[[str, bytes], Awaitable[VisualVerification]]


class Verifier:
    def __init__(self, vision_verifier: VisionVerifier | None = None):
        self.vision_verifier = vision_verifier

    async def verify(self, expectation: str, observation: Observation) -> VerificationResult:
        facts = _expected_facts(expectation)
        page_text = observation.page.text.casefold()
        present = tuple(fact for fact in facts if fact.casefold() in page_text)
        if facts and len(present) == len(facts):
            return VerificationResult(
                passed=True,
                evidence="DOM facts: " + "; ".join(present),
                confidence=1.0,
            )
        if self.vision_verifier is None:
            missing = tuple(fact for fact in facts if fact not in present)
            return VerificationResult(
                passed=False,
                evidence="Missing DOM facts: " + "; ".join(missing),
                confidence=1.0,
            )
        visual = await self.vision_verifier(expectation, observation.screenshot.path.read_bytes())
        return VerificationResult(
            passed=visual.passed,
            evidence=visual.evidence,
            used_vision=True,
            confidence=visual.confidence,
        )


def _expected_facts(expectation: str) -> tuple[str, ...]:
    quoted = re.findall(r"[“\"]([^”\"]+)[”\"]", expectation)
    money = [word.strip(".,") for word in expectation.split() if word.startswith("$")]
    coupon = [word for word in expectation.split() if word.isupper() and len(word) > 2]
    return tuple(dict.fromkeys(item for item in (*quoted, *money, *coupon) if item))
