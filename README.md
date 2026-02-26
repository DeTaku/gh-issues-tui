# gh-issues-tui

A minimal, fast, keyboard-driven terminal UI for GitHub Issues.  
Backed by the `gh` CLI — no OAuth code, no secret management.

```
dion-issues --repo OWNER/REPO
```

---

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | Uses `match`, `tomllib`, union types |
| [`gh` CLI](https://cli.github.com/) | Must be authenticated (`gh auth login`) |
| `windows-curses` | Windows only; installed automatically below |

---

## Install

```bash
# 1. Clone
git clone https://github.com/YOU/gh-issues-tui
cd gh-issues-tui

# 2. Create a virtualenv (recommended)
py -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Unix

# 3. Install the package + dependencies
pip install -e .

# 4. Authenticate with GitHub (if not already)
gh auth login
```

---

## Run

```bash
# Issue list — single repo
dion-issues --repo OWNER/REPO

# Or set a default and skip the flag every time
set DION_ISSUES_REPO=OWNER/REPO          # Windows (cmd)
$env:DION_ISSUES_REPO="OWNER/REPO"       # Windows (PowerShell)
export DION_ISSUES_REPO=OWNER/REPO       # Unix

dion-issues

# ── Feed mode ──────────────────────────────────────
# Combined issues + PRs, auto-refreshes every 60 s
dion-issues --feed --repo OWNER/REPO
dion-issues --feed --repo OWNER/REPO --repo OWNER2/REPO2   # multi-repo
dion-issues --feed --repo OWNER/REPO --label bug           # label filter
dion-issues --feed --repo OWNER/REPO --kind pr             # PRs only
dion-issues --feed --repo OWNER/REPO --author octocat      # author filter
dion-issues --feed --repo OWNER/REPO --refresh-interval 30 # faster refresh

# ── Notifications mode ─────────────────────────────
dion-issues --notif                                        # unread only
dion-issues --notif --all                                  # read + unread
dion-issues --notif --repo OWNER/REPO                      # specific repo
dion-issues --notif --kind PullRequest                     # PRs only
dion-issues --notif --reason mention                       # mentions only
dion-issues --notif --refresh-interval 60
```

---

## Configuration

All configuration is via environment variables (no config file needed):

| Variable | Default | Description |
|---|---|---|
| `DION_ISSUES_REPO` | – | Default `owner/repo`; overridden by `--repo` |
| `DION_ISSUES_TTL` | `300` | Cache TTL in seconds |
| `DION_ISSUES_CACHE_DIR` | `~/.cache/gh-issues-tui` | Where to store cached API responses |
| `DION_ISSUES_DATA_DIR` | `~/.local/share/gh-issues-tui` | Where to store draft comments |
| `EDITOR` | `notepad` (Win) / `vi` (Unix) | Editor for composing comments |

---

## Keys

### Issue list / Feed
| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `Enter` | Open issue / PR |
| `/` | Filter by text (ESC to clear) |
| `r` | Refresh (force) |
| `g` / `G` | Jump to top / bottom |
| `q` | Quit |

### Issue detail
| Key | Action |
|-----|--------|
| `j` / `k` | Scroll down / up |
| `g` / `G` | Jump to top / bottom |
| `c` | Compose / resume draft comment |
| `d` | Discard draft |
| `r` | Refresh issue + comments |
| `q` | Back to list |

### Notifications
| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `Enter` | Open issue / PR detail |
| `m` | Mark selected as read |
| `M` | Mark all visible as read |
| `/` | Filter by text (ESC to clear) |
| `r` | Force refresh |
| `q` | Quit |

---

## Run tests

```bash
pip install pytest
pytest tests/
```

---

## Data locations

- **Cache**: `~/.cache/gh-issues-tui/` — JSON files, safe to delete at any time.
- **Drafts**: `~/.local/share/gh-issues-tui/drafts.json` — plain JSON, human-readable.

---

## Dependency rationale

| Package | Why | What we lose without it |
|---------|-----|------------------------|
| `windows-curses` | Provides `_curses` C extension on Windows | App won't start on Windows |

No other external dependencies. Everything else uses the Python standard library.
