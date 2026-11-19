from __future__ import annotations

from difflib import SequenceMatcher

from pixelpilot.healing.fingerprint import Fingerprint, hamming_distance


def fingerprint_similarity(saved: Fingerprint, current: Fingerprint) -> float:
    tag = 1.0 if saved.tag == current.tag else 0.0
    role = 1.0 if saved.role == current.role else 0.0
    text = SequenceMatcher(None, saved.text, current.text).ratio()
    visual = 1.0 - hamming_distance(saved.phash, current.phash) / 64
    region = 1.0 if saved.region_hash == current.region_hash else 0.0
    return 0.15 * tag + 0.2 * role + 0.35 * text + 0.2 * visual + 0.1 * region
