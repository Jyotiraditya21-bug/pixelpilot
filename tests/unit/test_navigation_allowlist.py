from __future__ import annotations

from typing import Any, cast

import pytest

from pixelpilot.browser.actions import perform_action
from pixelpilot.models import ActionKind, ActionRequest


class NavigationPage:
    def __init__(self, redirect_to: str | None = None):
        self.url = "about:blank"
        self.redirect_to = redirect_to
        self.visited: list[str] = []

    async def goto(self, url: str, *, wait_until: str) -> None:
        assert wait_until == "domcontentloaded"
        self.visited.append(url)
        self.url = self.redirect_to or url


def navigation(url: str) -> ActionRequest:
    return ActionRequest(kind=ActionKind.NAVIGATE, intent="open target", value=url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    (
        "https://example.com",
        "http://localhost.evil.com",
        "http://localhost@evil.com",
        "http://user:password@localhost:8000",
        "javascript:alert(1)",
    ),
)
async def test_navigation_rejects_non_allowlisted_and_credential_urls(url: str) -> None:
    page = NavigationPage()
    result = await perform_action(cast(Any, page), navigation(url))
    assert not result.success
    assert "allowlist" in result.detail.casefold() or "credentials" in result.detail.casefold()
    assert page.visited == []


@pytest.mark.asyncio
async def test_navigation_rejects_redirect_to_non_allowlisted_host() -> None:
    page = NavigationPage(redirect_to="https://evil.example/landing")
    result = await perform_action(cast(Any, page), navigation("http://localhost:8000/redirect"))
    assert not result.success
    assert "redirect" in result.detail.casefold()
    assert page.visited == ["http://localhost:8000/redirect"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    (
        "http://localhost:8000/shop",
        "http://127.0.0.1:8000/cart",
        "http://[::1]:8000/checkout",
    ),
)
async def test_navigation_accepts_exact_loopback_hosts(url: str) -> None:
    page = NavigationPage()
    result = await perform_action(cast(Any, page), navigation(url))
    assert result.success
    assert page.visited == [url]
