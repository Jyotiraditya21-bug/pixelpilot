from __future__ import annotations

import json
from typing import Any, cast

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from pixelpilot.models import ActionKind, ActionRequest, ActionResult


async def perform_action(page: Page, action: ActionRequest) -> ActionResult:
    try:
        if action.kind == ActionKind.NAVIGATE:
            if action.value is None:
                raise ValueError("navigate requires a URL")
            await page.goto(action.value, wait_until="domcontentloaded")
        elif action.locator:
            locator = _resolve_cached_locator(page, action.locator)
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
                await _coordinate_click(page, x, y)
            elif action.kind == ActionKind.TYPE and action.value is not None:
                await page.mouse.click(x, y)
                await page.keyboard.insert_text(action.value)
            else:
                raise ValueError("coordinate grounding supports click or valued type")
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


def encode_cached_locator(action: ActionRequest) -> str | None:
    if action.role and action.name:
        payload = {"role": action.role, "name": action.name}
    elif action.text:
        payload = {"text": action.text}
    else:
        return None
    return "semantic:" + json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _resolve_cached_locator(page: Page, locator: str) -> object:
    payload = decode_cached_locator(locator)
    if payload is None:
        return page.locator(locator).first
    role = payload.get("role")
    name = payload.get("name")
    text = payload.get("text")
    if isinstance(role, str) and isinstance(name, str):
        return page.get_by_role(cast(Any, role), name=name, exact=False).first
    if isinstance(text, str):
        return page.get_by_text(text, exact=False).first
    raise ValueError("cached semantic locator has no target")


def decode_cached_locator(locator: str) -> dict[str, str] | None:
    if not locator.startswith("semantic:"):
        return None
    raw = json.loads(locator.removeprefix("semantic:"))
    if not isinstance(raw, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in raw.items()
    ):
        raise ValueError("invalid cached semantic locator")
    return cast(dict[str, str], raw)


async def _coordinate_click(page: Page, x: float, y: float) -> None:
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=3_000):
            await page.mouse.click(x, y)
    except PlaywrightTimeoutError:
        # The click may update the page without a document navigation.
        await page.wait_for_load_state("domcontentloaded", timeout=3_000)
