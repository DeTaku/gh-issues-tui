# gh-issues-tui — Engineering Intent & Project Summary

**Author:** DeTaku  
**Date:** February 2026  
**Status:** Working, tested, installable

---

## What this is

A keyboard-driven terminal application for reading and managing GitHub Issues,
Pull Requests, and Notifications — built deliberately in the spirit of
classic Unix tools like `mutt` (email) and `newsboat` (RSS).

The goal is not to replace the GitHub web UI.  The goal is to give a developer
who lives in the terminal a **fast, reliable, distraction-free interface** to
the things that matter: what issues are open, what needs a response, what
notifications are waiting.

It runs anywhere a terminal runs: SSH sessions, `tmux`, remote servers, CI
consoles — without a browser, without Electron, without a GUI toolkit.

---

## Why it was built this way

### 1. Lean over feature-rich

Every dependency is a maintenance liability.  This project has **one runtime
dependency** (`windows-curses`, only on Windows, only because Python's standard
library ships without the `_curses` C extension on that platform).

Everything else — HTTP networking, JSON parsing, terminal rendering, file I/O,
argument parsing, testing — uses the **Python standard library**.  There is no
web framework, no ORM, no async runtime, no UI toolkit beyond `curses`.

This is a deliberate application of YAGNI ("You Ain't Gonna Need It") and KISS
("Keep It Simple, Stupid").  Fewer moving parts means fewer things to break,
fewer security advisories to track, and faster cold-start.

### 2. No reinvented authentication

GitHub authentication is hard to get right: OAuth flows, token storage,
refresh logic, scopes, enterprise SSO.  Rather than implement any of that, the
app **delegates entirely to the `gh` CLI** (GitHub's own official tool).

If the user is authenticated with `gh`, the app works.  If not, it exits with a
clear message: `gh auth login`.  This means the app inherits GitHub's own
security model for free, and no credentials are ever stored by this software.

### 3. All API calls use JSON, never screen-scraped text

The official `gh api` subcommand returns raw JSON from the GitHub REST API.
The app only ever parses JSON.  It never reads human-formatted `gh issue list`
output, which would break silently on locale or format changes.  Every endpoint
used is [documented in the GitHub REST API reference](https://docs.github.com/en/rest).

### 4. Open data by default

Cache files and draft storage are **plain UTF-8 JSON on disk**.  Any user can
open, inspect, edit, or delete them with a text editor or `cat`.  No binary
formats, no SQLite databases, no proprietary serialisation.  This satisfies the
principle from [The five fundamental facets of ethical software](https://thinkmoult.com/five-fundamental-facets-of-ethical-software.html)
that data should be open and human-readable.

### 5. Code clarity over cleverness

The codebase follows the principles set out in
[Learn how to write good code](https://thinkmoult.com/clean-code-write.html):

- Every module has a single, clearly stated responsibility (see *Architecture*
  below).
- Every public function begins with a verb and names connote its return type.
- No function exceeds what it describes.
- No speculative abstractions: every layer that exists has a concrete, tested
  reason to exist.
- Failure modes are handled explicitly, not silently swallowed.

---

## Architecture

The codebase is intentionally flat.  There are no nested dependency chains, no
service locators, no dependency injection containers.

```
gh_issues/
  api.py           — all GitHub API calls (wraps `gh api`)
  cache.py         — SHA256-keyed TTL disk cache
  drafts.py        — local comment draft persistence
  feed.py          — unified issue+PR data model and filters
  notifications.py — notification data model and filters
  editor.py        — spawns $EDITOR for comment composition
  markdown.py      — minimal Markdown → terminal-lines renderer
  __main__.py      — CLI argument parsing, mode dispatch

  ui/
    app.py         — curses init, colour setup, top-level routing
    list_view.py   — issue list view
    detail_view.py — single issue/PR view + comment workflow
    feed_view.py   — combined live feed view
    notif_view.py  — notifications view

tests/
  test_cache.py         — 12 tests
  test_drafts.py        — 14 tests
  test_feed.py          — 17 tests
  test_notifications.py — 14 tests
  test_markdown.py      — 16 tests
                          ─────────
  Total                   75 tests, 0 failures
```

### Dependency flow (one-way, no cycles)

```
__main__ → ui/app → ui/{list,detail,feed,notif}_view
                  → api        (network)
                  → cache      (disk)
                  → drafts     (disk)
                  → markdown   (pure)
                  → editor     (subprocess)
                  → feed       (pure data)
                  → notifications (pure data)
```

`feed.py`, `notifications.py`, `markdown.py`, and `cache.py` have **zero
imports from within this project** — they are independently testable in
isolation, which is why the test suite can achieve full coverage of all
business logic without mocking curses at all.

---

## Feature summary

### Mode 1 — Issue list

The default mode.  Lists all open issues for a single repository, with number,
state badge, title, author, age, and a `[D]` marker when a local draft exists.
Supports real-time text filtering (`/`), cache-busting refresh (`r`), and
on-disk TTL caching so navigation is instant even on slow connections.

### Mode 2 — Issue detail

Opens a single issue showing title, metadata (state, labels, assignees, age),
body rendered from Markdown, and all comments in chronological order.  Fully
scrollable.

### Mode 3 — Feed (issues + pull requests, live)

A running combined feed across one or more repositories, sorted by
`updated_at` descending, auto-refreshing on a configurable interval (default
60 seconds).  Each item shows its type (`[I]` issue / `[PR]` pull request),
repo, number, title, author, age, and draft state.

CLI filters can pre-slice the feed by label, author, or kind before the app
starts.  An in-session `/` filter stacks on top of those.

### Mode 4 — Notifications

Shows the authenticated user's GitHub notification inbox.  Defaults to
**unread only**; `--all` includes already-read threads.  Can be scoped to
specific repositories, notification kinds (Issue, PullRequest, Release, etc.),
or reasons (mention, assign, review_requested, etc.).

Supports marking individual items or all visible items as read in one keypress,
which calls the GitHub API immediately and invalidates the local cache.

### Comment drafts

Draft comments are saved to disk automatically when the user exits the editor.
Drafts survive process exit.  Resuming a draft reopens `$EDITOR` pre-populated
with the saved text.  Submitting posts the comment via the GitHub API and
discards the draft.  Discarding prompts for confirmation before deleting.

### Caching

All API responses are cached as JSON files under `~/.cache/gh-issues-tui/`.
The cache key is a SHA-256 hash of the logical request string (e.g.
`issues:org/repo:open`).  Each file stores `{fetched_at, data}`.  TTL defaults
to 300 seconds and is configurable via `DION_ISSUES_TTL`.  Corrupt cache files
are silently deleted and treated as a miss, never crashing the app.

---

## Failure handling

| Scenario | Behaviour |
|----------|-----------|
| Not authenticated | Exit immediately with `gh auth login` instruction |
| Network unavailable | Serve stale cache; show `[offline]`; block comment submit |
| Rate limited | Surface the `gh` error message; return to view |
| Corrupt cache file | Delete file, treat as miss, re-fetch |
| Corrupt drafts file | Log warning to stderr, start with empty store |
| `$EDITOR` exits non-zero | Treat as cancelled; keep existing draft unchanged |
| Terminal resize | `KEY_RESIZE` handled in all views; layout reflows |

---

## What "done" means

The acceptance test (from the original specification) is:

> Open the app → list issues → open an issue → start a comment → save draft →
> quit → reopen → resume the draft → submit comment → see it appear on GitHub.

All steps of this workflow are implemented and the app remains usable between
network outages (cached browsing; commenting requires network to submit).

---

## What this is not

- It is not a GitHub project management tool.
- It does not create issues, close issues, or manage labels/milestones.
- It does not implement its own OAuth — `gh auth login` is the prerequisite.
- It does not render images, emoji shortcodes, or GitHub Flavored Markdown
  tables (those require a full HTML renderer, which would add a dependency).

These are not gaps; they are deliberate scope boundaries.  The value of saying
no to scope creep is a codebase that a new developer can read in an afternoon.

---

## How to run

```bash
git clone https://github.com/YOU/gh-issues-tui
cd gh-issues-tui
py -m pip install -e .       # or: pip install -e .
gh auth login                # once, if not already authenticated

dion-issues --repo OWNER/REPO                          # issue list
dion-issues --feed --repo OWNER/REPO                   # live feed
dion-issues --feed --repo ORG/A --repo ORG/B           # multi-repo feed
dion-issues --notif                                    # notifications
dion-issues --notif --reason mention --refresh-interval 60
```

Full option reference: `dion-issues --help`  
Full behaviour specification: [SPEC.md](SPEC.md)  
Living feature log: [FEATURES.md](FEATURES.md)
