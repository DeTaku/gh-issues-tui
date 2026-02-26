# gh-issues-tui — Feature Log

A living record of what the application can do, organised by mode.  
Each entry states the feature, the key/flag that activates it, and its current status.

---

## Release: 0.1.0 — February 2026

### Core infrastructure

| # | Feature | Status |
|---|---------|--------|
| I-1 | TTL disk cache for all API responses | ✅ |
| I-2 | Cache keyed by SHA-256 of logical request string | ✅ |
| I-3 | Configurable TTL via `DION_ISSUES_TTL` (default 300 s) | ✅ |
| I-4 | Configurable cache directory via `DION_ISSUES_CACHE_DIR` | ✅ |
| I-5 | Corrupt cache file handled gracefully (delete + re-fetch) | ✅ |
| I-6 | Manual cache invalidation on keypress `r` | ✅ |
| I-7 | Auth check at startup via `gh auth status`; clear error if not logged in | ✅ |
| I-8 | All API calls via `gh api` (JSON only; no screen-scraped output) | ✅ |
| I-9 | GitHub pagination handled (`--paginate` + `--jq .[]` NDJSON) | ✅ |

---

### Mode 1 — Issue list (`dion-issues --repo OWNER/REPO`)

| # | Feature | Key / Flag | Status |
|---|---------|-----------|--------|
| L-1 | List all open issues for a repository | — | ✅ |
| L-2 | Display: number, state badge (●/✓), title, author, age, draft marker | — | ✅ |
| L-3 | Closed issues displayed dimmed | — | ✅ |
| L-4 | Move cursor down / up | `j` / `k` or ↓ / ↑ | ✅ |
| L-5 | Jump to first / last item | `g` / `G` | ✅ |
| L-6 | Page down / up | `Space` / `PgUp` | ✅ |
| L-7 | Open selected issue in detail view | `Enter` | ✅ |
| L-8 | Real-time text filter by title, number, label, author | `/` then type | ✅ |
| L-9 | Clear filter | `ESC` | ✅ |
| L-10 | Force cache refresh (re-fetch from GitHub) | `r` | ✅ |
| L-11 | Show `[D]` marker when a local draft exists for an issue | — | ✅ |
| L-12 | Draft marker coloured yellow | — | ✅ |
| L-13 | Status bar: repo, issue count, cache age, position hint | — | ✅ |
| L-14 | Quit | `q` | ✅ |
| L-15 | Terminal resize handled without crash | `KEY_RESIZE` | ✅ |

---

### Mode 2 — Issue detail (opened from list or feed)

| # | Feature | Key / Flag | Status |
|---|---------|-----------|--------|
| D-1 | Display title, state, labels, assignees, author, age | — | ✅ |
| D-2 | Body rendered from Markdown (headings, bold, italic, code, links, lists, blockquotes, rules) | — | ✅ |
| D-3 | Fenced code blocks rendered with distinct colour and indentation | — | ✅ |
| D-4 | All comments shown in chronological order with author + age | — | ✅ |
| D-5 | Full-screen scroll | `j` / `k` | ✅ |
| D-6 | Jump to top / bottom | `g` / `G` | ✅ |
| D-7 | Page scroll | `Space` / `PgUp` | ✅ |
| D-8 | Scroll percentage shown in status bar | — | ✅ |
| D-9 | Force cache refresh (issue + comments) | `r` | ✅ |
| D-10 | Back to issue list | `q` | ✅ |
| D-11 | Terminal resize handled | `KEY_RESIZE` | ✅ |

#### Comment / draft workflow

| # | Feature | Key | Status |
|---|---------|-----|--------|
| C-1 | Open `$EDITOR` to compose a new comment | `c` | ✅ |
| C-2 | If a draft exists, pre-populate editor with saved text | `c` | ✅ |
| C-3 | Auto-save draft on editor exit (even if not submitted) | — | ✅ |
| C-4 | Prompt "Submit now? [y/N]" after editor closes | — | ✅ |
| C-5 | Post comment via `gh api POST` on confirmation | `y` | ✅ |
| C-6 | Discard draft and invalidate comments cache after successful post | — | ✅ |
| C-7 | API error on submit shown as overlay; draft retained | — | ✅ |
| C-8 | Resume draft on next `c` press (across process restarts) | `c` | ✅ |
| C-9 | Discard draft with Y/N confirmation | `d` | ✅ |
| C-10 | Draft saved at timestamp shown at bottom of detail view | — | ✅ |
| C-11 | Draft existence shown in title bar (`[DRAFT]`) | — | ✅ |
| C-12 | Drafts stored as plain JSON at `~/.local/share/gh-issues-tui/drafts.json` | — | ✅ |
| C-13 | Drafts keyed by `owner/repo#number` (no cross-repo collisions) | — | ✅ |
| C-14 | Editor resolved from `$VISUAL`, then `$EDITOR`, then platform default | — | ✅ |
| C-15 | Lines starting with `#` stripped from editor output (instruction lines) | — | ✅ |
| C-16 | Empty editor result treated as cancel (draft unchanged) | — | ✅ |

---

### Mode 3 — Feed (`dion-issues --feed`)

| # | Feature | Key / Flag | Status |
|---|---------|-----------|--------|
| F-1 | Combined issues + PRs for one or more repos | `--repo` (repeatable) | ✅ |
| F-2 | Sorted by `updated_at` descending (newest first) | — | ✅ |
| F-3 | Each item shows kind badge `[I]` / `[PR]`, repo, number, title, author, age | — | ✅ |
| F-4 | Draft PRs show `[draft]` annotation | — | ✅ |
| F-5 | Closed / merged items displayed dimmed | — | ✅ |
| F-6 | PRs and issues fetched from separate endpoints (no duplication) | — | ✅ |
| F-7 | Auto-refresh every N seconds without blocking the UI | `--refresh-interval N` | ✅ |
| F-8 | Default auto-refresh interval: 60 seconds | — | ✅ |
| F-9 | Countdown to next refresh shown in status bar | — | ✅ |
| F-10 | Force immediate refresh | `r` | ✅ |
| F-11 | CLI pre-filter by label (substring, case-insensitive) | `--label NAME` | ✅ |
| F-12 | CLI pre-filter by author login (substring) | `--author LOGIN` | ✅ |
| F-13 | CLI pre-filter by kind (issue or pr) | `--kind issue\|pr` | ✅ |
| F-14 | In-session text filter stacked on CLI filters | `/` then type | ✅ |
| F-15 | Open selected issue/PR in detail view | `Enter` | ✅ |
| F-16 | Return to feed after closing detail | `q` in detail | ✅ |
| F-17 | Separate cache keys per repo per kind (issues / PRs cached independently) | — | ✅ |
| F-18 | Failed repo fetch silently skipped if cache cold; shown if cache warm | — | ✅ |

---

### Mode 4 — Notifications (`dion-issues --notif`)

| # | Feature | Key / Flag | Status |
|---|---------|-----------|--------|
| N-1 | Show GitHub notification inbox | — | ✅ |
| N-2 | Default: unread only | — | ✅ |
| N-3 | Show read + unread | `--all` | ✅ |
| N-4 | Filter to specific repos | `--repo OWNER/REPO` (repeatable) | ✅ |
| N-5 | Filter by subject kind | `--kind Issue\|PullRequest\|Commit\|Release\|Discussion` | ✅ |
| N-6 | Filter by notification reason | `--reason mention\|assign\|review_requested\|…` | ✅ |
| N-7 | Auto-refresh every N seconds | `--refresh-interval N` | ✅ |
| N-8 | Default auto-refresh interval: 120 seconds | — | ✅ |
| N-9 | Countdown to next refresh in status bar | — | ✅ |
| N-10 | Each row shows: unread dot (●/○), kind badge, repo, title, reason, age | — | ✅ |
| N-11 | Unread dot and badge coloured for unread items | — | ✅ |
| N-12 | Read items displayed dimmed | — | ✅ |
| N-13 | Mark selected notification as read (calls GitHub API immediately) | `m` | ✅ |
| N-14 | Mark all visible notifications as read | `M` | ✅ |
| N-15 | Marking read invalidates cache; item disappears on next frame | — | ✅ |
| N-16 | Open issue / PR detail when notification links to one | `Enter` | ✅ |
| N-17 | In-session text filter by title, repo, reason | `/` then type | ✅ |
| N-18 | Force immediate refresh | `r` | ✅ |
| N-19 | Unread count shown in status bar | — | ✅ |
| N-20 | Terminal resize handled | `KEY_RESIZE` | ✅ |

---

## Planned / Possible future work

| # | Feature | Notes |
|---|---------|-------|
| P-1 | Closed issue list (`--state closed`) | API already supports it; needs a UI toggle |
| P-2 | Create new issue | Keeps scope lean; deliberate omission today |
| P-3 | Close / reopen issue | Same as above |
| P-4 | GitHub Flavored Markdown table rendering | Requires column-width accounting |
| P-5 | Emoji shortcode expansion (`:rocket:` → 🚀) | Nice-to-have; no runtime dep needed |
| P-6 | Issue timeline events (cross-references, label changes) | Separate `/timeline` endpoint |
| P-7 | Configurable colour themes | Today colours are hardcoded to a 256-colour minimum |
| P-8 | Mouse support | Conflicts with mutt/newsboat philosophy; probably not |

---

*This document is updated each time a feature ships.  Tick ✅ = implemented and tested.  Circle ○ = planned.  Cross ✗ = rejected with rationale.*
