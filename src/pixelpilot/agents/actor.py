from __future__ import annotations

from collections.abc import Awaitable, Callable

from playwright.async_api import Page

from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observation
from pixelpilot.browser.actions import perform_action
from pixelpilot.models import ActionRequest, ActionResult, GroundedAction

Replan = Callable[[ActionRequest, str], Awaitable[ActionRequest]]


class Actor:
    def __init__(self, grounder: Grounder):
        self.grounder = grounder

    async def act(
        self,
        page: Page,
        request: ActionRequest,
        observation: Observation,
        replan: Replan | None = None,
    ) -> tuple[ActionResult, GroundedAction]:
        grounded = await self.grounder.ground(request, observation)
        result = await perform_action(page, grounded.action)
        if result.success or replan is None:
            return result, grounded
        replacement = await replan(request, result.detail)
        grounded = await self.grounder.ground(replacement, observation)
        return await perform_action(page, grounded.action), grounded
