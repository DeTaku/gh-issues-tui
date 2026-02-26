"""Local draft storage for issue comments.

All drafts live in a single JSON file so they are trivial to inspect,
back up, or wipe.  The file format is:

    {
      "owner/repo#42": {
        "text":     "draft comment body",
        "saved_at": "2026-02-27T12:00:00Z"
      }
    }

Draft keys are "owner/repo#<number>" to avoid collisions across repos.
Corrupt or missing files are handled gracefully (treated as empty store).
"""

import json
import time
from pathlib import Path


class DraftStore:
    """Persist and retrieve comment drafts keyed by repo + issue number."""

    def __init__(self, store_path: Path):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, repo: str, number: int) -> str | None:
        """Return draft text for repo+issue, or None if no draft exists."""
        return self._load_all().get(self._key(repo, number), {}).get("text")

    def save(self, repo: str, number: int, text: str) -> None:
        """Persist draft text for repo+issue, stamped with UTC time."""
        drafts = self._load_all()
        drafts[self._key(repo, number)] = {
            "text": text,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._save_all(drafts)

    def discard(self, repo: str, number: int) -> None:
        """Remove draft for repo+issue (no-op if absent)."""
        drafts = self._load_all()
        if self._key(repo, number) in drafts:
            del drafts[self._key(repo, number)]
            self._save_all(drafts)

    def has_draft(self, repo: str, number: int) -> bool:
        """Return True if a non-empty draft exists for repo+issue."""
        text = self.load(repo, number)
        return bool(text and text.strip())

    def saved_at(self, repo: str, number: int) -> str | None:
        """Return the ISO timestamp string of the last save, or None."""
        return self._load_all().get(self._key(repo, number), {}).get("saved_at")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _key(self, repo: str, number: int) -> str:
        return f"{repo}#{number}"

    def _load_all(self) -> dict:
        if not self.store_path.exists():
            return {}
        try:
            return json.loads(self.store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt file — start fresh.  Warn to stderr.
            import sys
            print(
                f"Warning: draft store at {self.store_path} was corrupt; "
                "starting fresh.",
                file=sys.stderr,
            )
            return {}

    def _save_all(self, drafts: dict) -> None:
        self.store_path.write_text(
            json.dumps(drafts, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
