from __future__ import annotations

from pixelpilot.healing.cache import HealingCache
from pixelpilot.healing.fingerprint import Fingerprint
from pixelpilot.healing.strategies import fingerprint_similarity


class Healer:
    def __init__(self, cache: HealingCache, site: str, threshold: float = 0.72):
        self.cache = cache
        self.site = site
        self.threshold = threshold
        self.current: dict[str, Fingerprint] = {}

    def update_fingerprint(self, intent: str, fingerprint: Fingerprint) -> None:
        self.current[intent] = fingerprint

    async def locator_for(self, intent: str) -> str | None:
        entry = self.cache.get(self.site, intent)
        current = self.current.get(intent)
        if entry is None or current is None:
            return None
        if fingerprint_similarity(entry.fingerprint, current) < self.threshold:
            return None
        return entry.locator

    def enroll_validated(self, intent: str, locator: str, fingerprint: Fingerprint) -> None:
        self.cache.put(self.site, intent, locator, fingerprint)
