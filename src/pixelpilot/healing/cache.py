from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pixelpilot.healing.fingerprint import Fingerprint


@dataclass(frozen=True)
class CacheEntry:
    site: str
    intent: str
    locator: str
    fingerprint: Fingerprint
    successes: int


class HealingCache:
    def __init__(self, path: Path = Path(".pixelpilot/healing.db")):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS locator_cache (
                site TEXT NOT NULL, intent TEXT NOT NULL, locator TEXT NOT NULL,
                fingerprint TEXT NOT NULL, successes INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (site, intent))"""
            )

    def get(self, site: str, intent: str) -> CacheEntry | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT locator, fingerprint, successes FROM locator_cache "
                    "WHERE site=? AND intent=?",
                    (site, intent),
                ).fetchone()
            if row is None:
                return None
            return CacheEntry(
                site, intent, str(row[0]), Fingerprint.model_validate_json(row[1]), int(row[2])
            )
        except Exception:
            self.delete(site, intent)
            return None

    def put(self, site: str, intent: str, locator: str, fingerprint: Fingerprint) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO locator_cache(site,intent,locator,fingerprint) VALUES(?,?,?,?)
                ON CONFLICT(site,intent) DO UPDATE SET locator=excluded.locator,
                fingerprint=excluded.fingerprint,successes=locator_cache.successes+1,
                updated_at=CURRENT_TIMESTAMP""",
                (site, intent, locator, fingerprint.model_dump_json()),
            )

    def delete(self, site: str, intent: str) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM locator_cache WHERE site=? AND intent=?", (site, intent)
                )
        except Exception:
            pass

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection
