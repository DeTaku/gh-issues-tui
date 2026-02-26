"""Curses application entry point and shared application state.

Architecture:
  run(repo) → curses.wrapper(_main, repo)
  _main holds AppState and drives a simple two-state machine:
    "list"   → run_list_view()  returns ("open", number) | ("quit",)
    "detail" → run_detail_view() returns ("back",) | ("quit",)

  run_feed(repos, ...) → curses.wrapper(_main_feed, repos, ...)
  run_notif(...)       → curses.wrapper(_main_notif, ...)

AppState is a plain dataclass passed into every view.  Views read and
mutate it; they never talk to the cache or drafts directly — that is done
here in _main so the control flow stays in one place.
"""

import curses
import os
import sys
from pathlib import Path

from gh_issues.api import GhApiError, check_auth, fetch_issue, fetch_issues, fetch_comments
from gh_issues.cache import Cache
from gh_issues.drafts import DraftStore
from gh_issues.ui.colours import (
    CP_CODE, CP_DIM, CP_DRAFT, CP_HEAD1, CP_HEAD2, CP_LABEL, CP_SELECT, CP_STATUS,
    AppState, init_colours,
)
# View modules imported lazily inside _main/_main_feed/_main_notif to avoid
# any residual circular-import risk at module load time.


def run(repo: str) -> None:
    """Initialise curses and start the application."""
    try:
        check_auth()
    except GhApiError as exc:
        sys.exit(str(exc))
    curses.wrapper(_main, repo)


def _init_colours() -> None:
    """Set up the colour pairs used throughout the UI."""
    init_colours()


def _build_cache() -> Cache:
    cache_dir = Path(
        os.environ.get(
            "DION_ISSUES_CACHE_DIR",
            Path.home() / ".cache" / "gh-issues-tui",
        )
    )
    ttl = int(os.environ.get("DION_ISSUES_TTL", "300"))
    return Cache(cache_dir, ttl)


def _build_draft_store() -> DraftStore:
    data_dir = Path(
        os.environ.get(
            "DION_ISSUES_DATA_DIR",
            Path.home() / ".local" / "share" / "gh-issues-tui",
        )
    )
    return DraftStore(data_dir / "drafts.json")


def _load_issues(state: AppState) -> None:
    """Populate state.issues from cache or API."""
    cache_key = f"issues:{state.repo}:open"
    cached = state.cache.get(cache_key)
    if cached is not None:
        state.issues = cached
        state.issues_from_cache = True
        state.issues_cache_age = state.cache.age_seconds(cache_key)
        return
    issues = fetch_issues(state.repo, state="open")
    state.cache.set(cache_key, issues)
    state.issues = issues
    state.issues_from_cache = False
    state.issues_cache_age = 0.0


def _load_issue_detail(state: AppState, number: int) -> None:
    """Populate state.current_issue and state.current_comments."""
    issue_key = f"issue:{state.repo}:{number}"
    comments_key = f"comments:{state.repo}:{number}"

    cached_issue = state.cache.get(issue_key)
    cached_comments = state.cache.get(comments_key)

    if cached_issue is not None and cached_comments is not None:
        state.current_issue = cached_issue
        state.current_comments = cached_comments
        state.detail_from_cache = True
        return

    issue = fetch_issue(state.repo, number)
    comments = fetch_comments(state.repo, number)
    state.cache.set(issue_key, issue)
    state.cache.set(comments_key, comments)
    state.current_issue = issue
    state.current_comments = comments
    state.detail_from_cache = False


def _refresh_issues(state: AppState) -> None:
    """Bust issue list cache and re-fetch."""
    state.cache.invalidate(f"issues:{state.repo}:open")
    _load_issues(state)


def _refresh_issue_detail(state: AppState, number: int) -> None:
    """Bust detail cache and re-fetch."""
    state.cache.invalidate(f"issue:{state.repo}:{number}")
    state.cache.invalidate(f"comments:{state.repo}:{number}")
    _load_issue_detail(state, number)


def _main(stdscr: "curses.window", repo: str) -> None:
    """Main application loop."""
    from gh_issues.ui.list_view import run_list_view
    from gh_issues.ui.detail_view import run_detail_view
    _init_colours()
    curses.curs_set(0)
    stdscr.keypad(True)

    state = AppState(
        repo=repo,
        cache=_build_cache(),
        drafts=_build_draft_store(),
    )

    # Load issues with a loading message shown while waiting.
    _show_loading(stdscr, f"Loading issues for {repo}…")
    try:
        _load_issues(state)
    except GhApiError as exc:
        _show_fatal(stdscr, str(exc))
        return

    view = "list"
    current_number: int | None = None

    while True:
        if view == "list":
            action = run_list_view(stdscr, state)
            match action[0]:
                case "open":
                    current_number = action[1]
                    _show_loading(stdscr, f"Loading #{current_number}…")
                    try:
                        _load_issue_detail(state, current_number)
                    except GhApiError as exc:
                        _show_error(stdscr, str(exc))
                        continue
                    view = "detail"
                case "refresh":
                    _show_loading(stdscr, "Refreshing…")
                    try:
                        _refresh_issues(state)
                    except GhApiError as exc:
                        _show_error(stdscr, str(exc))
                case "quit":
                    break

        elif view == "detail" and current_number is not None:
            action = run_detail_view(stdscr, state, current_number)
            match action[0]:
                case "back":
                    view = "list"
                    state.current_issue = None
                    state.current_comments = []
                case "refresh":
                    _show_loading(stdscr, f"Refreshing #{current_number}…")
                    try:
                        _refresh_issue_detail(state, current_number)
                    except GhApiError as exc:
                        _show_error(stdscr, str(exc))
                case "quit":
                    break


# ------------------------------------------------------------------
# Transient overlay helpers
# ------------------------------------------------------------------

def _show_loading(stdscr: "curses.window", msg: str) -> None:
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    x = max(0, (w - len(msg)) // 2)
    y = h // 2
    try:
        stdscr.addstr(y, x, msg, curses.A_BOLD)
    except curses.error:
        pass
    stdscr.refresh()


def _show_error(stdscr: "curses.window", msg: str) -> None:
    h, w = stdscr.getmaxyx()
    lines = msg.splitlines()[:5]
    stdscr.erase()
    for i, line in enumerate(lines):
        try:
            stdscr.addstr(h // 2 - 2 + i, 2, line[:w - 4], curses.color_pair(CP_HEAD1))
        except curses.error:
            pass
    try:
        stdscr.addstr(h // 2 + 3, 2, "Press any key to continue…")
    except curses.error:
        pass
    stdscr.refresh()
    stdscr.getch()


def _show_fatal(stdscr: "curses.window", msg: str) -> None:
    _show_error(stdscr, msg)


# ------------------------------------------------------------------
# Feed entry point
# ------------------------------------------------------------------

def run_feed(
    repos: list[str],
    refresh_interval: int = 60,
    preset_label: str | None = None,
    preset_author: str | None = None,
    preset_kind: str | None = None,
) -> None:
    """Initialise curses and open the combined issues+PRs feed view."""
    try:
        check_auth()
    except GhApiError as exc:
        sys.exit(str(exc))
    curses.wrapper(
        _main_feed,
        repos, refresh_interval, preset_label, preset_author, preset_kind,
    )


def _main_feed(
    stdscr: "curses.window",
    repos: list[str],
    refresh_interval: int,
    preset_label: str | None,
    preset_author: str | None,
    preset_kind: str | None,
) -> None:
    from gh_issues.ui.feed_view import run_feed_view
    from gh_issues.ui.detail_view import run_detail_view

    _init_colours()
    curses.curs_set(0)
    stdscr.keypad(True)

    # A minimal AppState is still needed for cache + drafts.
    state = AppState(
        repo=repos[0] if repos else "",
        cache=_build_cache(),
        drafts=_build_draft_store(),
    )

    while True:
        action = run_feed_view(
            stdscr, state, repos,
            refresh_interval=refresh_interval,
            preset_label=preset_label,
            preset_author=preset_author,
            preset_kind=preset_kind,
        )
        match action[0]:
            case "open_issue":
                _, repo, number = action
                state.repo = repo
                _show_loading(stdscr, f"Loading {repo}#{number}…")
                try:
                    _load_issue_detail(state, number)
                except GhApiError as exc:
                    _show_error(stdscr, str(exc))
                    continue
                detail_action = run_detail_view(stdscr, state, number)
                _handle_detail_action(stdscr, state, detail_action, number)
            case "open_pr":
                # PRs use the same detail view via the issues API endpoint.
                _, repo, number = action
                state.repo = repo
                _show_loading(stdscr, f"Loading {repo}#{number}…")
                try:
                    _load_issue_detail(state, number)
                except GhApiError as exc:
                    _show_error(stdscr, str(exc))
                    continue
                run_detail_view(stdscr, state, number)
            case "quit":
                break


# ------------------------------------------------------------------
# Notifications entry point
# ------------------------------------------------------------------

def run_notif(
    filter_repos: list[str] | None = None,
    filter_kind: str | None = None,
    filter_reason: str | None = None,
    all_notifs: bool = False,
    refresh_interval: int = 120,
) -> None:
    """Initialise curses and open the notifications view."""
    try:
        check_auth()
    except GhApiError as exc:
        sys.exit(str(exc))
    curses.wrapper(
        _main_notif,
        filter_repos, filter_kind, filter_reason, all_notifs, refresh_interval,
    )


def _main_notif(
    stdscr: "curses.window",
    filter_repos: list[str] | None,
    filter_kind: str | None,
    filter_reason: str | None,
    all_notifs: bool,
    refresh_interval: int,
) -> None:
    from gh_issues.ui.notif_view import run_notif_view
    from gh_issues.ui.detail_view import run_detail_view

    _init_colours()
    curses.curs_set(0)
    stdscr.keypad(True)

    primary_repo = (filter_repos or [""])[0]
    state = AppState(
        repo=primary_repo,
        cache=_build_cache(),
        drafts=_build_draft_store(),
    )

    while True:
        action = run_notif_view(
            stdscr, state,
            filter_repos=filter_repos,
            filter_kind=filter_kind,
            filter_reason=filter_reason,
            all_notifs=all_notifs,
            refresh_interval=refresh_interval,
        )
        match action[0]:
            case "open_issue" | "open_pr":
                _, repo, number = action
                state.repo = repo
                _show_loading(stdscr, f"Loading {repo}#{number}…")
                try:
                    _load_issue_detail(state, number)
                except GhApiError as exc:
                    _show_error(stdscr, str(exc))
                    continue
                run_detail_view(stdscr, state, number)
            case "quit":
                break


# ------------------------------------------------------------------
# Shared detail-loop helper
# ------------------------------------------------------------------

def _handle_detail_action(
    stdscr: "curses.window",
    state: AppState,
    action: tuple,
    number: int,
) -> None:
    """Process a refresh action returned by run_detail_view. back/quit ignored."""
    if action[0] == "refresh":
        _show_loading(stdscr, f"Refreshing #{number}…")
        try:
            _refresh_issue_detail(state, number)
        except GhApiError as exc:
            _show_error(stdscr, str(exc))
