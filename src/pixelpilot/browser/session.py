from __future__ import annotations

import io
import shutil
from pathlib import Path

from PIL import Image
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from pixelpilot.models import Screenshot


class BrowserSession:
    def __init__(self, run_id: str, *, headless: bool = True, runs_dir: Path = Path("runs")):
        self.run_dir = runs_dir / run_id
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> BrowserSession:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            channel="chrome", headless=self.headless
        )
        self._context = await self._browser.new_context(viewport={"width": 1280, "height": 900})
        self.page = await self._context.new_page()
        return self

    async def __aexit__(self, _type: object, _value: object, _traceback: object) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self.prune_runs(self.run_dir.parent)

    def require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("Browser session is not open")
        return self.page

    async def screenshot(self, name: str) -> Screenshot:
        raw = await self.require_page().screenshot(type="jpeg", quality=60, full_page=False)
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        longest = max(image.size)
        if longest > 1024:
            scale = 1024 / longest
            image = image.resize(
                (round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS
            )
        path = self.run_dir / f"{name}.jpg"
        image.save(path, "JPEG", quality=60, optimize=True)
        return Screenshot(path=path, width=image.width, height=image.height)

    @staticmethod
    def prune_runs(runs_dir: Path, keep: int = 10) -> None:
        if not runs_dir.exists():
            return
        folders = sorted(
            (path for path in runs_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old in folders[keep:]:
            shutil.rmtree(old)
