from pathlib import Path

import pytest
from PIL import Image

from pixelpilot.healing.cache import HealingCache
from pixelpilot.healing.fingerprint import Fingerprint, average_hash, hamming_distance
from pixelpilot.healing.strategies import fingerprint_similarity


def _fingerprint(text: str = "buy") -> Fingerprint:
    return Fingerprint(tag="button", role="button", text=text, region_hash="abc", phash="0" * 16)


def test_average_hash_and_hamming_distance() -> None:
    white = average_hash(Image.new("RGB", (20, 20), "white"))
    black = average_hash(Image.new("RGB", (20, 20), "black"))
    assert len(white) == 16
    assert hamming_distance(white, white) == 0
    assert hamming_distance(white, black) == 0


def test_similarity_prefers_matching_semantics() -> None:
    assert fingerprint_similarity(_fingerprint(), _fingerprint()) == pytest.approx(1.0)
    assert fingerprint_similarity(_fingerprint(), _fingerprint("unrelated field")) < 1.0


def test_sqlite_cache_is_keyed_by_site_and_intent(tmp_path: Path) -> None:
    cache = HealingCache(tmp_path / "healing.db")
    cache.put("shop.example", "buy mug", "button.cached", _fingerprint())
    entry = cache.get("shop.example", "buy mug")
    assert entry is not None
    assert entry.locator == "button.cached"
    assert cache.get("other.example", "buy mug") is None
