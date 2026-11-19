from __future__ import annotations

from dataclasses import dataclass

from pixelpilot.browser.dom_snapshot import snapshot_page
from pixelpilot.browser.session import BrowserSession
from pixelpilot.models import PageSnapshot, Screenshot


@dataclass(frozen=True)
class Observation:
    page: PageSnapshot
    screenshot: Screenshot


class Observer:
    async def observe(self, session: BrowserSession, step: int) -> Observation:
        page = session.require_page()
        snapshot = await snapshot_page(page)
        screenshot = await session.screenshot(f"step-{step:02d}")
        return Observation(page=snapshot, screenshot=screenshot)
