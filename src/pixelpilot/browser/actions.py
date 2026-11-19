from __future__ import annotations

from typing import Any, cast

from playwright.async_api import Page

from pixelpilot.models import ActionKind, ActionRequest, ActionResult


async def perform_action(page: Page, action: ActionRequest) -> ActionResult:
    try:
        if action.kind == ActionKind.NAVIGATE:
            if action.value is None:
                raise ValueError("navigate requires a URL")
            await page.goto(action.value, wait_until="domcontentloaded")
        elif action.locator:
            locator = page.locator(action.locator).first
            await _use_locator(locator, action)
        elif action.role and action.name:
            locator = page.get_by_role(cast(Any, action.role), name=action.name, exact=False).first
            await _use_locator(locator, action)
        elif action.text:
            locator = page.get_by_text(action.text, exact=False).first
            await _use_locator(locator, action)
        elif action.bbox:
            x, y = action.bbox.center
            if action.kind == ActionKind.CLICK:
                await page.mouse.click(x, y)
            else:
                raise ValueError("coordinate grounding only supports click")
        else:
            raise ValueError("action has no usable target")
        return ActionResult(success=True, detail="action completed")
    except Exception as exc:  # Playwright exposes several runtime exception types.
        return ActionResult(success=False, detail=f"{type(exc).__name__}: {exc}")


async def _use_locator(locator: object, action: ActionRequest) -> None:
    from playwright.async_api import Locator

    if not isinstance(locator, Locator):
        raise TypeError("expected Playwright locator")
    if action.kind == ActionKind.CLICK:
        await locator.click(timeout=5_000)
    elif action.kind == ActionKind.TYPE:
        if action.value is None:
            raise ValueError("type requires a value")
        await locator.fill(action.value, timeout=5_000)
    else:
        raise ValueError(f"unsupported locator action: {action.kind}")
