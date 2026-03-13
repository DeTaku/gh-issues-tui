"""Issue list view.

Displays a scrollable, filterable list of issues.  Returns an action
tuple to app.py upon exit.

Keys:
    j / DOWN    move cursor down
    k / UP      move cursor up
    g           jump to top
    G           jump to bottom
    Enter       open selected issue → ("open", number)
    /           start search filter (type to filter, ESC to clear)
    r           refresh             → ("refresh",)
    q           quit                → ("quit",)
    KEY_RESIZE  adapt to new terminal size
"""

import curses
import math
from datetime import datetime, timezone

from gh_issues.ui.colours import (
    CP_CODE, CP_DIM, CP_DRAFT, CP_HEAD1, CP_LABEL, CP_SELECT, CP_STATUS, AppState
)

# Width of the issue-number column (e.g. "  #1234  ")
_NUM_COL = 7
# Width of the state badge ("● " or "✓ ")
_STATE_COL = 2
# Width of the age column ("  3d ")
_AGE_COL = 6
# Width of the author column
_AUTHOR_COL = 14


def run_list_view(stdscr: "curses.window", state: AppState) -> tuple:
    """Run the issue list view. Returns an action tuple."""
    while True:
        h, w = stdscr.getmaxyx()
        visible_issues = _apply_filter(state.issues, state.search)
        state.cursor = max(0, min(state.cursor, len(visible_issues) - 1))
        _draw_list(stdscr, state, visible_issues, h, w)

        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            curses.update_lines_cols()
            continue

        if state.search:
            # We're in search mode — handle text input.
            action = _handle_search_key(key, state)
            if action:
                return action
            continue

        action = _handle_normal_key(key, state, visible_issues, h)
        if action:
            return action


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------

def _draw_list(
    stdscr: "curses.window",
    state: AppState,
    visible: list[dict],
    h: int,
    w: int,
) -> None:
    stdscr.erase()
    content_rows = h - 2  # title row + status row

    # Ensure scroll window keeps cursor visible.
    if state.cursor < state.scroll_top:
        state.scroll_top = state.cursor
    if state.cursor >= state.scroll_top + content_rows:
        state.scroll_top = state.cursor - content_rows + 1

    # Title row
    title = f" {state.repo}"
    if state.search:
        title += f"  /{state.search}"
    _draw_hline(stdscr, 0, title, w, curses.color_pair(CP_STATUS) | curses.A_BOLD)

    # Issue rows
    for row_idx in range(content_rows):
        issue_idx = state.scroll_top + row_idx
        screen_row = row_idx + 1
        if issue_idx >= len(visible):
            try:
                stdscr.move(screen_row, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass
            continue
        issue = visible[issue_idx]
        is_selected = issue_idx == state.cursor
        has_draft = state.drafts.has_draft(state.repo, issue["number"])
        _draw_issue_row(stdscr, screen_row, issue, is_selected, has_draft, w, state)

    # Status bar
    total = len(state.issues)
    shown = len(visible)
    cache_label = _cache_label(state.issues_from_cache, state.issues_cache_age)
    pos = f"{state.cursor + 1}/{shown}" if shown else "0/0"
    if shown < total:
        count_text = f"{shown}/{total} issues  {cache_label}  {pos}"
    else:
        count_text = f"{total} issues  {cache_label}  {pos}"
    hint = "j/k:move  Enter:open  r:refresh  /:filter  q:quit"
    status = f" {count_text}   {hint}"
    _draw_hline(stdscr, h - 1, status, w, curses.color_pair(CP_STATUS))
    stdscr.refresh()


def _draw_issue_row(
    stdscr: "curses.window",
    row: int,
    issue: dict,
    is_selected: bool,
    has_draft: bool,
    w: int,
    state: AppState,
) -> None:
    is_closed = issue.get("state") == "closed"
    base_attr = curses.A_REVERSE if is_selected else 0
    dim_attr  = curses.color_pair(CP_DIM) | curses.A_DIM if (is_closed and not is_selected) else base_attr

    number  = f"#{issue['number']:>4}"
    badge   = "✓" if is_closed else "●"
    age     = _format_age(issue.get("created_at", ""))
    author  = (issue.get("user") or {}).get("login", "")[:_AUTHOR_COL]
    draft_m = "[D]" if has_draft else "   "

    title_width = max(10, w - _NUM_COL - _STATE_COL - _AUTHOR_COL - _AGE_COL - 6)
    title = issue.get("title", "")[:title_width].ljust(title_width)

    line = f" {number} {badge} {title} {author:<{_AUTHOR_COL}} {age:>{_AGE_COL}} {draft_m}"
    line = line[:w - 1]

    try:
        if is_selected:
            stdscr.addstr(row, 0, line.ljust(w - 1), curses.color_pair(CP_SELECT) | curses.A_BOLD)
        elif is_closed:
            stdscr.addstr(row, 0, line, curses.color_pair(CP_DIM) | curses.A_DIM)
        else:
            stdscr.addstr(row, 0, line)
            # Colour draft marker yellow when present
            if has_draft:
                draft_col = len(line) - 3
                stdscr.addstr(row, draft_col, "[D]", curses.color_pair(CP_DRAFT) | curses.A_BOLD)
    except curses.error:
        pass


# ------------------------------------------------------------------
# Key handling
# ------------------------------------------------------------------

def _handle_normal_key(
    key: int,
    state: AppState,
    visible: list[dict],
    h: int,
) -> tuple | None:
    content_rows = h - 2

    if key in (ord("j"), curses.KEY_DOWN):
        state.cursor = min(state.cursor + 1, max(0, len(visible) - 1))
    elif key in (ord("k"), curses.KEY_UP):
        state.cursor = max(state.cursor - 1, 0)
    elif key == ord("g"):
        state.cursor = 0
    elif key == ord("G"):
        state.cursor = max(0, len(visible) - 1)
    elif key in (curses.KEY_NPAGE, ord(" ")):
        state.cursor = min(state.cursor + content_rows - 1, max(0, len(visible) - 1))
    elif key in (curses.KEY_PPAGE,):
        state.cursor = max(state.cursor - content_rows + 1, 0)
    elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        if visible:
            return ("open", visible[state.cursor]["number"])
    elif key == ord("r"):
        return ("refresh",)
    elif key == ord("/"):
        state.search = "/"  # enter search mode
    elif key == ord("q"):
        return ("quit",)
    return None


def _handle_search_key(key: int, state: AppState) -> tuple | None:
    if key == 27:  # ESC
        state.search = ""
        state.cursor = 0
    elif key in (curses.KEY_BACKSPACE, ord("\b"), 127):
        if len(state.search) > 1:
            state.search = state.search[:-1]
        else:
            state.search = ""
            state.cursor = 0
    elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        visible = _apply_filter(state.issues, state.search)
        state.cursor = 0
        # Stay in search mode but "confirm" (do nothing special)
    elif 32 <= key <= 126:
        if state.search == "/":
            state.search = chr(key)
        else:
            state.search += chr(key)
        state.cursor = 0
    elif key == ord("q") and not state.search:
        return ("quit",)
    return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _apply_filter(issues: list[dict], search: str) -> list[dict]:
    query = search.lstrip("/").lower().strip()
    if not query:
        return issues
    return [
        i for i in issues
        if query in i.get("title", "").lower()
        or query in str(i.get("number", ""))
        or any(query in (lbl.get("name") or "").lower() for lbl in i.get("labels", []))
        or query in (i.get("user") or {}).get("login", "").lower()
    ]


def _format_age(iso: str) -> str:
    """Return human-readable age ('3d', '2w', '4mo') from ISO 8601 string."""
    if not iso:
        return ""
    try:
        created = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_seconds = (now - created).total_seconds()
        days = int(delta_seconds / 86400)
        if days < 1:
            return "<1d"
        if days < 14:
            return f"{days}d"
        if days < 60:
            return f"{days // 7}w"
        if days < 365:
            return f"{days // 30}mo"
        return f"{days // 365}y"
    except (ValueError, TypeError):
        return ""


def _cache_label(from_cache: bool, age: float | None) -> str:
    if not from_cache:
        return "live"
    if age is None:
        return "cached"
    if age < 60:
        return f"cached {int(age)}s"
    return f"cached {int(age // 60)}m"


def _draw_hline(
    stdscr: "curses.window",
    row: int,
    text: str,
    w: int,
    attr: int,
) -> None:
    line = text[:w - 1].ljust(w - 1)
    try:
        stdscr.addstr(row, 0, line, attr)
    except curses.error:
        pass
