"""Notifications view.

Shows GitHub notification threads for the authenticated user.
Auto-refreshes using a non-blocking getch timeout loop.

Keys:
    j / k / g / G    move / jump
    Enter            open item detail (if issue/PR in a watched repo)
    m                mark selected notification as read
    M                mark all visible as read
    u                toggle unread-only / show-all
    r                force refresh
    /                search / filter (ESC to clear)
    q                quit

Returns action tuples:
    ("open_issue",  repo, number)
    ("open_pr",     repo, number)
    ("quit",)
"""

import curses
import time

from gh_issues.api import GhApiError, fetch_notifications, mark_notification_read
from gh_issues.cache import Cache
from gh_issues.notifications import NotifItem, build_notif_items, filter_notifs
from gh_issues.ui.colours import (
    CP_DIM, CP_DRAFT, CP_HEAD1, CP_HEAD2, CP_LABEL, CP_SELECT, CP_STATUS,
    AppState,
)
from gh_issues.ui.list_view import _draw_hline, _format_age

_POLL_MS         = 500
_REFRESH_SECONDS = 120  # notifications auto-refresh interval

# Abbreviated reason labels shown in the UI.
_REASON_SHORT: dict[str, str] = {
    "assign":           "assigned",
    "author":           "author",
    "comment":          "comment",
    "invitation":       "invite",
    "manual":           "manual",
    "mention":          "mention",
    "review_requested": "review",
    "security_alert":   "security",
    "state_change":     "state",
    "subscribed":       "subscribed",
    "team_mention":     "team",
    "your_activity":    "you",
}

_KIND_BADGE: dict[str, str] = {
    "Issue":       "[I] ",
    "PullRequest": "[PR]",
    "Commit":      "[C] ",
    "Release":     "[R] ",
    "Discussion":  "[D] ",
}


def run_notif_view(
    stdscr: "curses.window",
    state: AppState,
    filter_repos: list[str] | None = None,
    filter_kind: str | None = None,
    filter_reason: str | None = None,
    all_notifs: bool = False,
    refresh_interval: int = _REFRESH_SECONDS,
) -> tuple:
    """Run the notifications view.  Returns an action tuple."""
    items: list[NotifItem] = []
    last_fetch: float = 0.0
    cursor = 0
    scroll_top = 0
    search = ""
    show_all = all_notifs  # can be toggled at runtime with 'u'

    stdscr.timeout(_POLL_MS)

    while True:
        now = time.monotonic()
        if (now - last_fetch) >= refresh_interval:
            items = _fetch_notifs(state.cache, show_all, refresh_interval)
            last_fetch = time.monotonic()

        h, w = stdscr.getmaxyx()
        visible = filter_notifs(
            items,
            repos=filter_repos or None,
            kind=filter_kind or None,
            reason=filter_reason or None,
            search=search.lstrip("/") or None,
            unread_only=not show_all,
        )
        cursor = max(0, min(cursor, len(visible) - 1))
        next_in = max(0, int(refresh_interval - (time.monotonic() - last_fetch)))
        _draw_notif(stdscr, visible, cursor, scroll_top, search,
                    show_all, next_in, h, w)
        scroll_top = _clamp_scroll(cursor, scroll_top, h - 2)

        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            curses.update_lines_cols()
            continue

        if key == -1:
            continue

        if search:
            result = _handle_search_key(key, search)
            if result == "clear":
                search = ""
                cursor = 0
            elif result == "quit":
                return ("quit",)
            else:
                search = result
                cursor = 0
            continue

        action = _handle_normal_key(key, cursor, visible, h)

        match action[0]:
            case "cursor":
                cursor = action[1]
            case "search":
                search = "/"
                cursor = 0
            case "refresh":
                last_fetch = 0.0
            case "mark_one":
                if visible:
                    _mark_read(state.cache, visible[cursor])
                    items = [i for i in items if i.thread_id != visible[cursor].thread_id]
            case "mark_all":
                for item in visible:
                    _mark_read(state.cache, item)
                read_ids = {i.thread_id for i in visible}
                items = [i for i in items if i.thread_id not in read_ids]
                cursor = 0
            case "toggle_all":
                show_all = not show_all
                last_fetch = 0.0  # force re-fetch with new all_notifs value
                cursor = 0
            case "open":
                item = action[1]
                if item.kind == "Issue" and item.issue_number:
                    return ("open_issue", item.repo, item.issue_number)
                if item.kind == "PullRequest" and item.issue_number:
                    return ("open_pr", item.repo, item.issue_number)
            case "quit":
                return ("quit",)


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------

_CACHE_KEY = "notifications"


def _fetch_notifs(cache: Cache, all_notifs: bool, ttl: int) -> list[NotifItem]:
    key = f"{_CACHE_KEY}:all={all_notifs}"
    cached = cache.get(key)
    if cached is not None:
        return build_notif_items(cached)
    try:
        raw = fetch_notifications(all_notifs=all_notifs)
        cache.set(key, raw)
        return build_notif_items(raw)
    except GhApiError:
        return []


def _mark_read(cache: Cache, item: NotifItem) -> None:
    try:
        mark_notification_read(item.thread_id)
        cache.invalidate(f"{_CACHE_KEY}:all=False")
        cache.invalidate(f"{_CACHE_KEY}:all=True")
    except GhApiError:
        pass


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------

_REASON_COL = 10
_KIND_COL   = 4
_REPO_MAX   = 22
_AGE_COL    = 6


def _draw_notif(
    stdscr: "curses.window",
    visible: list[NotifItem],
    cursor: int,
    scroll_top: int,
    search: str,
    show_all: bool,
    next_in: int,
    h: int,
    w: int,
) -> None:
    stdscr.erase()
    content_rows = h - 2

    scope = "all" if show_all else "unread"
    title = f" NOTIFICATIONS  ({scope})"
    if search and search != "/":
        title += f"  /{search.lstrip('/')}"   
    _draw_hline(stdscr, 0, title, w, curses.color_pair(CP_STATUS) | curses.A_BOLD)

    unread_count = sum(1 for i in visible if i.unread)
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
        _draw_notif_row(stdscr, screen_row, visible[item_idx],
                        item_idx == cursor, w)

    total = len(visible)
    pos = f"{cursor + 1}/{total}" if total else "0/0"
    status = (
        f" {unread_count} unread  {pos}  refresh in {next_in}s"
        f"   j/k:move  Enter:open  m:read  M:read-all  u:toggle-all  /:filter  q:quit"
    )
    _draw_hline(stdscr, h - 1, status, w, curses.color_pair(CP_STATUS))
    stdscr.refresh()


def _draw_notif_row(
    stdscr: "curses.window",
    row: int,
    item: NotifItem,
    is_selected: bool,
    w: int,
) -> None:
    unread_dot = "●" if item.unread else "○"
    badge      = _KIND_BADGE.get(item.kind, "[?] ")
    reason     = _REASON_SHORT.get(item.reason, item.reason)[:_REASON_COL]
    repo       = item.repo[:_REPO_MAX].ljust(_REPO_MAX)
    age        = _format_age(item.updated_at)

    title_width = max(10, w - _REPO_MAX - _REASON_COL - _AGE_COL - 14)
    title = item.title[:title_width].ljust(title_width)

    line = f" {unread_dot} {badge} {repo} {title} {reason:<{_REASON_COL}} {age:>{_AGE_COL}}"
    line = line[:w - 1]

    try:
        if is_selected:
            stdscr.addstr(row, 0, line.ljust(w - 1),
                          curses.color_pair(CP_SELECT) | curses.A_BOLD)
        elif not item.unread:
            stdscr.addstr(row, 0, line, curses.color_pair(CP_DIM) | curses.A_DIM)
        else:
            stdscr.addstr(row, 0, line)
            # Colour the unread dot and badge for unread items.
            stdscr.addstr(row, 1, unread_dot, curses.color_pair(CP_HEAD1) | curses.A_BOLD)
            if item.kind == "PullRequest":
                stdscr.addstr(row, 3, badge, curses.color_pair(CP_HEAD2))
    except curses.error:
        pass


# ------------------------------------------------------------------
# Key handling
# ------------------------------------------------------------------

def _handle_normal_key(
    key: int,
    cursor: int,
    visible: list[NotifItem],
    h: int,
) -> tuple:
    n = len(visible)
    content_rows = h - 2

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
    if key == ord("m"):
        return ("mark_one",)
    if key == ord("M"):
        return ("mark_all",)
    if key == ord("u"):
        return ("toggle_all",)
    if key == ord("r"):
        return ("refresh",)
    if key == ord("/"):
        return ("search",)
    if key == ord("q"):
        return ("quit",)
    return ("noop",)


def _handle_search_key(key: int, search: str) -> str:
    if key == 27:
        return "clear"
    if key in (curses.KEY_BACKSPACE, ord("\b"), 127):
        return search[:-1] if len(search) > 1 else "clear"
    if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
        return search
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
