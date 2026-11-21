from __future__ import annotations

import httpx
import pytest
from demo_app.main import app


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo.test") as value:
        yield value


@pytest.mark.asyncio
async def test_scroll_fixture(client: httpx.AsyncClient) -> None:
    for mutate in (False, True):
        response = await client.get("/scroll", params={"mutate": int(mutate)})
        assert response.status_code == 200
        assert "Confirm bottom action" in response.text

        response = await client.post("/scroll", data={"mutate": int(mutate)})
        assert response.status_code == 200
        assert "Scroll target reached and confirmed" in response.text


@pytest.mark.asyncio
async def test_modal_fixture(client: httpx.AsyncClient) -> None:
    for mutate in (False, True):
        client.cookies.clear()
        response = await client.get("/modal", params={"mutate": int(mutate)})
        assert response.status_code == 200
        assert "Cookie Consent" in response.text

        response = await client.post(
            "/modal", data={"action": "accept_cookies", "mutate": int(mutate)}
        )
        assert response.status_code == 200
        assert response.cookies["accepted_cookies"] == "1"

        response = await client.post("/modal", data={"action": "claim_deal", "mutate": int(mutate)})
        assert response.status_code == 200
        assert "Special deal claimed successfully" in response.text


@pytest.mark.asyncio
async def test_ambiguous_fixture(client: httpx.AsyncClient) -> None:
    for mutate in (False, True):
        response = await client.get("/ambiguous", params={"mutate": int(mutate)})
        assert response.status_code == 200
        assert "Target Widget" in response.text

        response = await client.post(
            "/ambiguous", data={"item": "Target Widget", "mutate": int(mutate)}
        )
        assert response.status_code == 200
        assert "Target Widget added to cart" in response.text


@pytest.mark.asyncio
async def test_icons_fixture(client: httpx.AsyncClient) -> None:
    for mutate in (False, True):
        response = await client.get("/icons", params={"mutate": int(mutate)})
        assert response.status_code == 200
        assert "🛒" in response.text

        response = await client.post("/icons", data={"icon": "cart", "mutate": int(mutate)})
        assert response.status_code == 200
        assert "Cart icon selected" in response.text
