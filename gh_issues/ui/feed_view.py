"""Combined issue + pull request feed view.

Supports one or more repos.  Auto-refreshes every `refresh_interval`
seconds using a non-blocking getch timeout loop.

Keys:
    j / DOWN    move down
    k / UP      move up
    g / G       jump to top / bottom
    Enter       open item (issue or PR detail)
    /           search / filter (ESC to clear)
    r           force refresh now
    q           quit

Returns action tuples to app.py:
    ("open_issue",  repo, number)
    ("open_pr",     repo, number)
    ("quit",)
"""

import curses
import time

from gh_issues.cache import Cache
from gh_issues.api import GhApiError, fetch_issues, fetch_pull_requests
from gh_issues.feed import FeedItem, build_feed, filter_feed, sort_feed
from gh_issues.ui.colours import (
    CP_CODE, CP_DIM, CP_DRAFT, CP_HEAD1, CP_HEAD2, CP_LABEL, CP_SELECT, CP_STATUS,
    AppState,
)
from gh_issues.ui.list_view import _draw_hline, _format_age

_POLL_MS = 500  # getch poll interval while waiting for auto-refresh


def run_feed_view(
    stdscr: "curses.window",
    state: AppState,
    repos: list[str],
    refresh_interval: int = 60,
    preset_label: str | None = None,
    preset_author: str | None = None,
    preset_kind: str | None = None,
) -> tuple:
    """Run the feed view.  Returns an action tuple."""
    items: list[FeedItem] = []
    last_fetch: float = 0.0
    cursor = 0
    scroll_top = 0
    search = ""

    stdscr.timeout(_POLL_MS)  # non-blocking getch for auto-refresh

    while True:
        now = time.monotonic()
        need_refresh = (now - last_fetch) >= refresh_interval

        if need_refresh:
            items = _fetch_feed(state.cache, repos)
            last_fetch = time.monotonic()

        h, w = stdscr.getmaxyx()
        visible = filter_feed(
            items,
            kind=preset_kind or None,
            label=preset_label or None,
            author=preset_author or None,
            search=search or None,
        )
        visible = sort_feed(visible)
        cursor = max(0, min(cursor, len(visible) - 1))
        next_refresh_in = max(0, int(refresh_interval - (time.monotonic() - last_fetch)))
        _draw_feed(stdscr, visible, cursor, scroll_top, search, repos,
                   next_refresh_in, h, w)
        scroll_top = _clamp_scroll(cursor, scroll_top, h - 2)

        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            curses.update_lines_cols()
            continue

        if key == -1:
            # Timeout — loop to check for auto-refresh.
            continue

        if search and search != "/":
            result = _handle_search_key_feed(key, search)
            if isinstance(result, str):
                search = result
                cursor = 0
            elif result == "clear":
                search = ""
                cursor = 0
            elif result == "quit":
                return ("quit",)
            continue

        action = _handle_normal_key_feed(key, cursor, scroll_top, visible, h)
        if isinstance(action, tuple):
            if action[0] == "cursor":
                cursor = action[1]
            elif action[0] == "search":
                search = "/"
                cursor = 0
            elif action[0] == "refresh":
                last_fetch = 0.0  # force re-fetch on next loop
            elif action[0] == "open":
                item = action[1]
                if item.kind == "issue":
                    return ("open_issue", item.repo, item.number)
                return ("open_pr", item.repo, item.number)
            elif action[0] == "quit":
                return ("quit",)


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------

def _fetch_feed(cache: Cache, repos: list[str]) -> list[FeedItem]:
    """Fetch issues + PRs for all repos, using cache."""
    all_items: list[FeedItem] = []
    for repo in repos:
        issues_key = f"feed_issues:{repo}"
        prs_key    = f"feed_prs:{repo}"

        raw_issues = cache.get(issues_key)
        if raw_issues is None:
            try:
                raw_issues = fetch_issues(repo, state="open")
                cache.set(issues_key, raw_issues)
            except GhApiError:
                raw_issues = []

        raw_prs = cache.get(prs_key)
        if raw_prs is None:
            try:
                raw_prs = fetch_pull_requests(repo, state="open")
                cache.set(prs_key, raw_prs)
            except GhApiError:
                raw_prs = []

        all_items.extend(build_feed(raw_issues + raw_prs, repo))
    return all_items


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------

_KIND_BADGE = {"issue": "[I] ", "pr": "[PR]"}
_STATE_COLOUR = {"open": 0, "closed": CP_DIM, "merged": CP_HEAD2}

_AUTHOR_COL = 14
_AGE_COL    = 6
_REPO_MAX   = 20


def _draw_feed(
    stdscr: "curses.window",
    visible: list[FeedItem],
    cursor: int,
    scroll_top: int,
    search: str,
    repos: list[str],
    next_refresh_in: int,
    h: int,
    w: int,
) -> None:
    stdscr.erase()
    content_rows = h - 2

    repo_label = ", ".join(repos) if len(repos) <= 2 else f"{len(repos)} repos"
    title = f" FEED  {repo_label}"
    if search:
        title += f"  /{search}"
    _draw_hline(stdscr, 0, title, w, curses.color_pair(CP_STATUS) | curses.A_BOLD)

    for row_idx in range(content_rows):
        item_idx = scroll_top + row_idx
        screen_row = row_idx + 1
        if item_idx >= len(visible):
            try:
                stdscr.move(screen_row, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass
            continue
        _draw_feed_row(stdscr, screen_row, visible[item_idx],
                       item_idx == cursor, w)

    total = len(visible)
    pos = f"{cursor + 1}/{total}" if total else "0/0"
    status = (
        f" {pos}  refresh in {next_refresh_in}s"
        f"   j/k:move  Enter:open  r:refresh now  /:filter  q:quit"
    )
    _draw_hline(stdscr, h - 1, status, w, curses.color_pair(CP_STATUS))
    stdscr.refresh()


def _draw_feed_row(
    stdscr: "curses.window",
    row: int,
    item: FeedItem,
    is_selected: bool,
    w: int,
) -> None:
    badge = _KIND_BADGE.get(item.kind, "[?] ")
    age = _format_age(item.updated_at)
    repo = item.repo[:_REPO_MAX].ljust(_REPO_MAX)
    number = f"#{item.number:>4}"
    author = item.author[:_AUTHOR_COL]
    draft_mark = "[draft]" if item.is_draft else ""

    title_width = max(10, w - _REPO_MAX - _AUTHOR_COL - _AGE_COL - 20)
    title = item.title[:title_width].ljust(title_width)

    line = f" {badge} {repo} {number} {title} {author:<{_AUTHOR_COL}} {age:>{_AGE_COL}} {draft_mark}"
    line = line[:w - 1]

    try:
        if is_selected:
            stdscr.addstr(row, 0, line.ljust(w - 1),
                          curses.color_pair(CP_SELECT) | curses.A_BOLD)
        elif item.state != "open":
            stdscr.addstr(row, 0, line, curses.color_pair(CP_DIM) | curses.A_DIM)
        else:
            stdscr.addstr(row, 0, line)
            if item.kind == "pr":
                stdscr.addstr(row, 1, badge, curses.color_pair(CP_HEAD2))
    except curses.error:
        pass


# ------------------------------------------------------------------
# Key handling
# ------------------------------------------------------------------

def _handle_normal_key_feed(
    key: int,
    cursor: int,
    scroll_top: int,
    visible: list[FeedItem],
    h: int,
) -> tuple:
    content_rows = h - 2
    n = len(visible)

    if key in (ord("j"), curses.KEY_DOWN):
        return ("cursor", min(cursor + 1, max(0, n - 1)))
    if key in (ord("k"), curses.KEY_UP):
        return ("cursor", max(cursor - 1, 0))
    if key == ord("g"):
        return ("cursor", 0)
    if key == ord("G"):
        return ("cursor", max(0, n - 1))
    if key in (curses.KEY_NPAGE, ord(" ")):
        return ("cursor", min(cursor + content_rows - 1, max(0, n - 1)))
    if key == curses.KEY_PPAGE:
        return ("cursor", max(cursor - content_rows + 1, 0))
    if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        if visible:
            return ("open", visible[cursor])
    if key == ord("r"):
        return ("refresh",)
    if key == ord("/"):
        return ("search",)
    if key == ord("q"):
        return ("quit",)
    return ("noop",)


def _handle_search_key_feed(key: int, search: str) -> str | str:
    if key == 27:
        return "clear"
    if key in (curses.KEY_BACKSPACE, ord("\b"), 127):
        return search[:-1] if len(search) > 1 else "clear"
    if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        return search  # confirm, stay in search
    if key == ord("q") and not search:
        return "quit"
    if 32 <= key <= 126:
        return (search if search != "/" else "") + chr(key)
    return search


def _clamp_scroll(cursor: int, scroll_top: int, content_rows: int) -> int:
    if cursor < scroll_top:
        return cursor
    if cursor >= scroll_top + content_rows:
        return cursor - content_rows + 1
    return scroll_top
