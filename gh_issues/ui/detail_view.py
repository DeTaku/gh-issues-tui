"""Issue detail view.

Renders one issue: header, body (Markdown), then each comment.
Supports scrolling, comment composition, and draft management.

Keys:
    j / DOWN    scroll down
    k / UP      scroll up
    g / G       jump to top / bottom
    c           compose comment (opens $EDITOR; resumes draft if present)
    d           discard current draft (Y/N prompt)
    r           refresh             → ("refresh",)
    q           back to list        → ("back",)
    KEY_RESIZE  adapt to new terminal size
"""

import curses

from gh_issues.api import GhApiError, post_comment
from gh_issues.editor import compose_comment
from gh_issues.markdown import RenderedLine, render
from gh_issues.markdown import (
    STYLE_CODE, STYLE_DIM, STYLE_HEADING1, STYLE_HEADING2,
    STYLE_HEADING3, STYLE_NORMAL, STYLE_RULE,
)
from gh_issues.ui.colours import (
    CP_CODE, CP_DIM, CP_DRAFT, CP_HEAD1, CP_HEAD2, CP_SELECT, CP_STATUS,
    AppState,
)
from gh_issues.ui.list_view import _cache_label, _draw_hline, _format_age

_SEPARATOR = "─" * 60


def run_detail_view(
    stdscr: "curses.window",
    state: AppState,
    number: int,
) -> tuple:
    """Run the issue detail view. Returns an action tuple."""
    scroll = 0

    while True:
        h, w = stdscr.getmaxyx()
        lines = _build_lines(state, number, w - 2)
        content_rows = h - 2
        max_scroll = max(0, len(lines) - content_rows)
        scroll = max(0, min(scroll, max_scroll))
        _draw_detail(stdscr, state, number, lines, scroll, h, w)

        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            curses.update_lines_cols()
            continue

        if key in (ord("j"), curses.KEY_DOWN):
            scroll = min(scroll + 1, max_scroll)
        elif key in (ord("k"), curses.KEY_UP):
            scroll = max(scroll - 1, 0)
        elif key == ord("g"):
            scroll = 0
        elif key == ord("G"):
            scroll = max_scroll
        elif key in (curses.KEY_NPAGE, ord(" ")):
            scroll = min(scroll + content_rows - 1, max_scroll)
        elif key == curses.KEY_PPAGE:
            scroll = max(scroll - content_rows + 1, 0)
        elif key == ord("r"):
            return ("refresh",)
        elif key == ord("q"):
            return ("back",)
        elif key == ord("c"):
            action = _do_compose(stdscr, state, number)
            if action:
                return action
            # Re-enter loop (view is redrawn on next iteration).
        elif key == ord("d"):
            _do_discard_draft(stdscr, state, number)


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------

def _build_lines(state: AppState, number: int, width: int) -> list[RenderedLine]:
    """Build the flat list of RenderedLines for the full issue view."""
    issue = state.current_issue
    if issue is None:
        return [RenderedLine("No issue loaded.", STYLE_NORMAL)]

    lines: list[RenderedLine] = []

    # --- Header ---
    title = issue.get("title", "(no title)")
    lines.append(RenderedLine(f"#{number}  {title}", STYLE_HEADING1))
    lines.append(RenderedLine("", STYLE_NORMAL))

    state_label = issue.get("state", "").upper()
    author = (issue.get("user") or {}).get("login", "?")
    age = _format_age(issue.get("created_at", ""))
    labels = ", ".join(lbl.get("name", "") for lbl in issue.get("labels", []))
    assignees = ", ".join(
        a.get("login", "") for a in issue.get("assignees", [])
    )

    lines.append(RenderedLine(f"State: {state_label}   Author: {author}   {age}", STYLE_DIM))
    if labels:
        lines.append(RenderedLine(f"Labels: {labels}", STYLE_DIM))
    if assignees:
        lines.append(RenderedLine(f"Assignees: {assignees}", STYLE_DIM))
    lines.append(RenderedLine("", STYLE_NORMAL))
    lines.append(RenderedLine(_SEPARATOR, STYLE_RULE))
    lines.append(RenderedLine("", STYLE_NORMAL))

    # --- Body ---
    body = issue.get("body") or "(no description)"
    lines.extend(render(body, width))
    lines.append(RenderedLine("", STYLE_NORMAL))

    # --- Comments ---
    for comment in state.current_comments:
        lines.append(RenderedLine(_SEPARATOR, STYLE_RULE))
        c_author = (comment.get("user") or {}).get("login", "?")
        c_age = _format_age(comment.get("created_at", ""))
        lines.append(RenderedLine(f"{c_author}   {c_age}", STYLE_HEADING2))
        lines.append(RenderedLine("", STYLE_NORMAL))
        c_body = comment.get("body") or ""
        lines.extend(render(c_body, width))
        lines.append(RenderedLine("", STYLE_NORMAL))

    # --- Draft indicator ---
    if state.drafts.has_draft(state.repo, number):
        saved_at = state.drafts.saved_at(state.repo, number) or ""
        lines.append(RenderedLine(_SEPARATOR, STYLE_RULE))
        lines.append(RenderedLine(
            f"[DRAFT saved {saved_at}  —  press c to edit, d to discard]",
            STYLE_DIM,
        ))

    return lines


def _draw_detail(
    stdscr: "curses.window",
    state: AppState,
    number: int,
    lines: list[RenderedLine],
    scroll: int,
    h: int,
    w: int,
) -> None:
    stdscr.erase()
    content_rows = h - 2

    # Title row
    has_draft = state.drafts.has_draft(state.repo, number)
    draft_mark = " [DRAFT]" if has_draft else ""
    cache_label = _cache_label(state.detail_from_cache, None)
    title_text = f" {state.repo}  #{number}{draft_mark}  {cache_label}"
    _draw_hline(stdscr, 0, title_text, w, curses.color_pair(CP_STATUS) | curses.A_BOLD)

    # Content
    for row_idx in range(content_rows):
        line_idx = scroll + row_idx
        screen_row = row_idx + 1
        if line_idx >= len(lines):
            try:
                stdscr.move(screen_row, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass
            continue
        rl = lines[line_idx]
        _draw_rendered_line(stdscr, screen_row, rl, w)

    # Scroll indicator
    total = len(lines)
    pct = int(100 * (scroll + content_rows) / total) if total else 100
    pct = min(pct, 100)

    hint = "j/k:scroll  c:comment  d:discard  r:refresh  q:back"
    status = f" {pct}%  {hint}"
    _draw_hline(stdscr, h - 1, status, w, curses.color_pair(CP_STATUS))
    stdscr.refresh()


def _draw_rendered_line(
    stdscr: "curses.window",
    row: int,
    rl: RenderedLine,
    w: int,
) -> None:
    text = rl.text[:w - 2]
    attr = _style_to_attr(rl.style)
    try:
        stdscr.addstr(row, 1, text, attr)
    except curses.error:
        pass


def _style_to_attr(style: str) -> int:
    match style:
        case "heading1":
            return curses.color_pair(CP_HEAD1) | curses.A_BOLD
        case "heading2":
            return curses.color_pair(CP_HEAD2) | curses.A_BOLD
        case "heading3":
            return curses.A_BOLD
        case "code":
            return curses.color_pair(CP_CODE)
        case "dim":
            return curses.color_pair(CP_DIM) | curses.A_DIM
        case "rule":
            return curses.color_pair(CP_DIM) | curses.A_DIM
        case _:
            return 0


# ------------------------------------------------------------------
# Comment workflow
# ------------------------------------------------------------------

def _do_compose(
    stdscr: "curses.window",
    state: AppState,
    number: int,
) -> tuple | None:
    """Open $EDITOR; save draft; optionally submit.  Returns action or None."""
    initial = state.drafts.load(state.repo, number) or ""

    # Suspend curses while the editor runs.
    curses.endwin()
    try:
        text = compose_comment(initial_text=initial)
    finally:
        # Restore curses.
        stdscr.refresh()

    if text is None:
        # Editor was closed with empty buffer — keep existing draft unchanged.
        return None

    # Auto-save draft.
    state.drafts.save(state.repo, number, text)

    # Prompt: submit now?
    answer = _prompt_yn(stdscr, "Submit comment now? [y/N] ")
    if answer:
        return _submit_comment(stdscr, state, number, text)
    return None  # Draft saved; return to detail view.


def _submit_comment(
    stdscr: "curses.window",
    state: AppState,
    number: int,
    text: str,
) -> tuple | None:
    """Post comment to GitHub; discard draft on success."""
    _draw_overlay(stdscr, "Posting comment…")
    try:
        post_comment(state.repo, number, text)
        state.drafts.discard(state.repo, number)
        # Invalidate comments cache so refresh shows the new comment.
        state.cache.invalidate(f"comments:{state.repo}:{number}")
        return ("refresh",)
    except GhApiError as exc:
        _draw_overlay(stdscr, f"Error posting comment:\n{exc}\n\nPress any key…")
        stdscr.getch()
        return None


def _do_discard_draft(
    stdscr: "curses.window",
    state: AppState,
    number: int,
) -> None:
    if not state.drafts.has_draft(state.repo, number):
        _draw_overlay(stdscr, "No draft to discard.  Press any key…")
        stdscr.getch()
        return
    if _prompt_yn(stdscr, "Discard draft? [y/N] "):
        state.drafts.discard(state.repo, number)


# ------------------------------------------------------------------
# Overlay helpers
# ------------------------------------------------------------------

def _prompt_yn(stdscr: "curses.window", prompt: str) -> bool:
    """Show a prompt and return True if the user presses 'y' or 'Y'."""
    h, w = stdscr.getmaxyx()
    row = h - 1
    try:
        stdscr.addstr(row, 0, prompt[:w - 1].ljust(w - 1), curses.color_pair(CP_STATUS) | curses.A_BOLD)
    except curses.error:
        pass
    curses.curs_set(1)
    stdscr.refresh()
    key = stdscr.getch()
    curses.curs_set(0)
    return key in (ord("y"), ord("Y"))


def _draw_overlay(stdscr: "curses.window", msg: str) -> None:
    h, w = stdscr.getmaxyx()
    lines = msg.splitlines()
    for i, line in enumerate(lines[:5]):
        row = h // 2 - 2 + i
        try:
            stdscr.addstr(row, 2, line[:w - 4], curses.A_BOLD)
        except curses.error:
            pass
    stdscr.refresh()
