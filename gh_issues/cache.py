"""Disk-backed TTL cache for GitHub API responses.

Design:
  - Each entry is stored as a JSON file under cache_dir.
  - The filename is derived from a SHA-256 hash of the cache key.
  - Each file contains {"fetched_at": <unix_timestamp>, "data": <payload>}.
  - Entries older than ttl_seconds are treated as stale (not deleted
    automatically; only replaced on the next set() call).
  - Cache files are plain JSON and safe to inspect or delete manually.

Invalidation strategy:
  - Time-based TTL: configurable, default 300 s (5 minutes).
  - Manual invalidation: call invalidate(key) or invalidate_all().
  - A refresh keypress in the UI calls invalidate() before re-fetching.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_TTL_SECONDS = 300


class Cache:
    """TTL-based disk cache backed by JSON files."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return cached data if present and within TTL, else None."""
        path = self._key_to_path(key)
        envelope = self._read_envelope(path)
        if envelope is None:
            return None
        age = time.time() - envelope.get("fetched_at", 0)
        if age > self.ttl_seconds:
            return None
        return envelope.get("data")

    def set(self, key: str, data: Any) -> None:
        """Write data to cache stamped with the current time."""
        envelope = {"fetched_at": time.time(), "data": data}
        self._key_to_path(key).write_text(
            json.dumps(envelope), encoding="utf-8"
        )

    def invalidate(self, key: str) -> None:
        """Remove a single cache entry (no-op if absent)."""
        self._key_to_path(key).unlink(missing_ok=True)

    def invalidate_all(self) -> None:
        """Remove every cache entry under cache_dir."""
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)

    def age_seconds(self, key: str) -> float | None:
        """Return the age of a cache entry in seconds, or None if absent."""
        path = self._key_to_path(key)
        envelope = self._read_envelope(path)
        if envelope is None:
            return None
        return time.time() - envelope.get("fetched_at", 0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _key_to_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _read_envelope(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt file — treat as cache miss.
            path.unlink(missing_ok=True)
            return None
