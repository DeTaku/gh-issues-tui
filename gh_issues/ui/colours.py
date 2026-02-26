"""Curses colour pair indices and AppState — imported by all view modules.

Kept in a separate module so view files can import these constants without
triggering a circular import with ui/app.py.
"""

import curses
from dataclasses import dataclass, field
from pathlib import Path


# ------------------------------------------------------------------
# Colour pair indices — defined once, used everywhere
# ------------------------------------------------------------------
CP_STATUS = 1   # Status bar
CP_SELECT = 2   # Selected row
CP_DIM    = 3   # Dim text (closed issues, metadata)
CP_HEAD1  = 4   # Heading level 1
CP_HEAD2  = 5   # Heading level 2
CP_CODE   = 6   # Code text
CP_LABEL  = 7   # GitHub labels
CP_DRAFT  = 8   # Draft indicator


def init_colours() -> None:
    """Initialise curses colour pairs. Call once after curses.start_color()."""
    curses.start_color()
    curses.use_default_colors()
    bg = -1

    curses.init_pair(CP_STATUS, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(CP_SELECT, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(CP_DIM,    curses.COLOR_WHITE, bg)
    curses.init_pair(CP_HEAD1,  curses.COLOR_YELLOW, bg)
    curses.init_pair(CP_HEAD2,  curses.COLOR_CYAN,   bg)
    curses.init_pair(CP_CODE,   curses.COLOR_GREEN,  bg)
    curses.init_pair(CP_LABEL,  curses.COLOR_GREEN,  bg)
    curses.init_pair(CP_DRAFT,  curses.COLOR_YELLOW, bg)


# ------------------------------------------------------------------
# Shared application state
# ------------------------------------------------------------------

@dataclass
class AppState:
    repo: str
    cache: "Cache"   # gh_issues.cache.Cache — typed as string to avoid import
    drafts: "DraftStore"
    # Populated by _load_issues()
    issues: list[dict] = field(default_factory=list)
    issues_from_cache: bool = False
    issues_cache_age: float | None = None
    # List-view UI state
    cursor: int = 0
    scroll_top: int = 0
    search: str = ""
    # Detail-view data (loaded lazily)
    current_issue: dict | None = None
    current_comments: list[dict] = field(default_factory=list)
    detail_from_cache: bool = False
