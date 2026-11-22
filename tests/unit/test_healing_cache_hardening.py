from __future__ import annotations

import concurrent.futures
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from pixelpilot.agents.observer import Observation
from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.browser.actions import encode_cached_locator
from pixelpilot.healing.cache import HealingCache
from pixelpilot.healing.fingerprint import Fingerprint, fingerprint_element
from pixelpilot.models import (
    ActionKind,
    ActionRequest,
    BBox,
    ElementSnapshot,
    PageSnapshot,
    Screenshot,
)


def _dummy_fingerprint(text: str = "submit") -> Fingerprint:
    return Fingerprint(
        tag="button",
        role="button",
        text=text,
        region_hash="abc",
        phash="0" * 16,
    )


def test_corrupted_sqlite_row_is_handled_gracefully_and_evicted(tmp_path: Path) -> None:
    db_path = tmp_path / "healing.db"
    cache = HealingCache(db_path)

    # Insert a valid entry
    cache.put("example.com", "submit form", "button.submit", _dummy_fingerprint())
    assert cache.get("example.com", "submit form") is not None

    # Corrupt the fingerprint column in SQLite directly with malformed JSON
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE locator_cache SET fingerprint = 'CORRUPTED_NOT_JSON' WHERE site = 'example.com'"
        )

    # Getting the corrupted entry should not raise an exception, but return None and delete it
    entry = cache.get("example.com", "submit form")
    assert entry is None

    # Confirm it was evicted from the database
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM locator_cache WHERE site = 'example.com'").fetchone()
        assert row is None


def test_concurrent_writes_succeed_without_database_locked(tmp_path: Path) -> None:
    db_path = tmp_path / "healing.db"
    HealingCache(db_path)

    def write_worker(worker_id: int) -> None:
        c = HealingCache(db_path)
        for i in range(25):
            c.put(
                f"site-{worker_id}.com",
                f"intent-{i}",
                f"button-{i}",
                _dummy_fingerprint(f"text-{i}"),
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(write_worker, i) for i in range(8)]
        for f in concurrent.futures.as_completed(futures):
            f.result()  # Should not raise sqlite3.OperationalError: database is locked

    # Verify rows were written
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT count(*) FROM locator_cache").fetchone()[0]
        assert count == 8 * 25


@pytest.mark.asyncio
async def test_fingerprint_mismatch_evicts_cache_entry(tmp_path: Path) -> None:
    cache = HealingCache(tmp_path / "healing.db")
    action = ActionRequest(
        kind=ActionKind.CLICK,
        intent="checkout",
        role="button",
        name="Checkout",
    )
    locator = encode_cached_locator(action)
    assert locator is not None

    # Put an entry with fingerprint expecting text "Pay Now"
    cache.put(
        "shop.test",
        action.intent,
        locator,
        Fingerprint(
            tag="button",
            role="button",
            text="pay now",
            region_hash="original_hash",
            phash="f" * 16,
        ),
    )

    # Create observation where element has changed completely to "Cancel Order"
    img_path = tmp_path / "shot.jpg"
    Image.new("RGB", (100, 100), "black").save(img_path, "JPEG")
    obs = Observation(
        page=PageSnapshot(
            url="https://shop.test/cart",
            title="Cart",
            text="Cancel Order",
            elements=(
                ElementSnapshot(
                    tag="button",
                    role="button",
                    name="Cancel Order",
                    text="Cancel Order",
                    bbox=BBox(x=10, y=10, width=80, height=30),
                ),
            ),
            viewport_width=100,
            viewport_height=100,
        ),
        screenshot=Screenshot(path=img_path, width=100, height=100),
    )

    orchestrator = Orchestrator(healing_cache=cache)
    result = await orchestrator._cached_locator(action.intent, obs)
    assert result is None
    # Entry should be evicted
    assert cache.get("shop.test", action.intent) is None


@pytest.mark.asyncio
async def test_cache_hit_on_changed_bounding_box_region(tmp_path: Path) -> None:
    cache = HealingCache(tmp_path / "healing.db")
    action = ActionRequest(
        kind=ActionKind.CLICK,
        intent="checkout",
        role="button",
        name="Checkout",
    )
    locator = encode_cached_locator(action)
    assert locator is not None

    # Element was originally at (10, 10, 80, 30)
    original_el = ElementSnapshot(
        tag="button",
        role="button",
        name="Checkout",
        text="Checkout",
        bbox=BBox(x=10, y=10, width=80, height=30),
    )
    img_path = tmp_path / "shot.jpg"
    img = Image.new("RGB", (200, 200), "white")
    img.save(img_path, "JPEG")
    img_bytes = img_path.read_bytes()

    original_fp = fingerprint_element(img_bytes, original_el, 200, 200)
    cache.put("shop.test", action.intent, locator, original_fp)

    # Now in the mutated page, the button shifted to (100, 150, 80, 30)
    mutated_el = ElementSnapshot(
        tag="button",
        role="button",
        name="Checkout",
        text="Checkout",
        bbox=BBox(x=100, y=150, width=80, height=30),
    )
    obs = Observation(
        page=PageSnapshot(
            url="https://shop.test/cart",
            title="Cart",
            text="Checkout",
            elements=(mutated_el,),
            viewport_width=200,
            viewport_height=200,
        ),
        screenshot=Screenshot(path=img_path, width=200, height=200),
    )

    orchestrator = Orchestrator(healing_cache=cache)
    cached_result = await orchestrator._cached_locator(action.intent, obs)

    # Must resolve successfully as a cache hit despite moved bbox
    assert cached_result == locator
    assert cache.get("shop.test", action.intent) is not None
