"""Spawn $EDITOR for comment composition and return the result.

The workflow:
  1. Write initial_text to a temp file.
  2. Suspend curses (endwin), spawn the editor, wait for it to exit.
  3. Read the file back; strip the optional marker comment.
  4. Return the edited text, or None if the file is unchanged / empty.

Platform notes:
  - On Windows, $EDITOR defaults to "notepad" if unset.
  - On Unix, defaults to "vi" if neither $VISUAL nor $EDITOR is set.
  - The function does NOT re-enter curses; that is the caller's job.

Public surface:
    compose_comment(initial_text, suffix) -> str | None
"""

import os
import sys
import tempfile
from pathlib import Path

_MARKER = "# --- Write your comment above this line. Lines starting with '#' are removed. ---"


def compose_comment(initial_text: str = "", suffix: str = ".md") -> str | None:
    """Open an editor with initial_text; return the final text or None.

    Returns None if the user saved an empty buffer or did not change the
    placeholder.  Strips lines that begin with '#' (used for instructions).
    """
    editor = _resolve_editor()
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=suffix,
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(initial_text)
        if not initial_text.endswith("\n"):
            tmp.write("\n")
        tmp.write("\n")
        tmp.write(_MARKER + "\n")

    try:
        exit_code = os.system(f'{editor} "{tmp_path}"')
        if exit_code != 0:
            return None
        return _read_result(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _resolve_editor() -> str:
    """Return the editor command to use, never empty."""
    editor = (
        os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or ("notepad" if sys.platform == "win32" else "vi")
    )
    return editor


def _read_result(path: Path) -> str | None:
    """Read edited text; strip marker lines; return None if effectively empty."""
    raw = path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if not line.startswith("#")]
    text = "\n".join(lines).strip()
    return text if text else None
