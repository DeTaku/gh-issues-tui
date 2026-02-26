# gh-issues-tui — Behaviour Spec

## Purpose
A keyboard-driven terminal UI for reading and commenting on GitHub Issues,
backed by the `gh` CLI for auth and API access.

## Views

### Issue List
Displays open issues for a repo: number, state badge, title, author.
Paginated issues are loaded in full at startup (cached on disk).

### Issue Detail
Displays one issue: title, metadata (state / labels / assignees / created-at),
body rendered as plain text, then all comments in chronological order.

## Keybindings

| Key       | Context | Action                                      |
|-----------|---------|---------------------------------------------|
| `j` / ↓   | both    | Move cursor / scroll down                   |
| `k` / ↑   | both    | Move cursor / scroll up                     |
| `Enter`   | list    | Open selected issue                         |
| `q`       | list    | Quit                                        |
| `q`       | detail  | Back to list                                |
| `r`       | both    | Refresh (invalidate cache, re-fetch)        |
| `/`       | list    | Enter search filter (ESC to clear)          |
| `c`       | detail  | Compose comment (resume draft if present)  |
| `d`       | detail  | Discard current draft (prompts Y/N)         |
| `ESC`     | list    | Clear search filter                         |
| `g` / `G` | both    | Jump to top / bottom                        |

## Comment workflow
1. Press `c` on an issue detail view.
2. If a draft exists, `$EDITOR` opens pre-populated with the draft text.
3. Save and quit `$EDITOR`; app auto-saves the result as a new draft.
4. If the buffer is non-empty, app prompts "Submit comment? [y/N]".
5. On `y`, the comment is posted via `gh api`; draft is discarded.
6. On `n`, the text is saved as a draft and the user returns to the detail view.
7. `d` in the detail view discards any saved draft after Y/N confirmation.

## Status line (bottom of screen)
List:   `owner/repo  •  42 open  •  live  •  j/k:move  Enter:open  r:refresh  /:filter  q:quit`
Detail: `owner/repo  #123  •  cached 3m  •  j/k:scroll  c:comment  d:discard  q:back`

## Configuration
| Env var                  | Default       | Purpose                            |
|--------------------------|---------------|------------------------------------|
| `DION_ISSUES_REPO`       | –             | Default owner/repo (skip --repo)   |
| `DION_ISSUES_TTL`        | 300           | Cache TTL in seconds               |
| `DION_ISSUES_CACHE_DIR`  | `~/.cache/gh-issues-tui` | Cache directory       |
| `DION_ISSUES_DATA_DIR`   | `~/.local/share/gh-issues-tui` | Drafts store    |
| `EDITOR`                 | `notepad` (Win) / `vi` (Unix) | Comment editor |

---

## Feed mode

```
dion-issues --feed --repo OWNER/REPO [--repo OWNER2/REPO2 ...]
```

Shows a running, auto-refreshing list of open issues **and** pull requests
combined, sorted by `updated_at` descending.  Multiple repos are interleaved.

### Feed filters (CLI flags)
| Flag | Purpose |
|------|---------|
| `--label NAME`    | Include only items carrying this label (substring, case-insensitive) |
| `--author LOGIN`  | Include only items by this author (substring) |
| `--kind issue\|pr` | Restrict to issues or PRs only |
| `--refresh-interval N` | Auto-refresh every N seconds (default 60) |

### Feed keybindings
Same as the issue list, plus:
| Key | Action |
|-----|--------|
| `/` | In-session text filter (stacks with CLI filters) |
| `r` | Force immediate refresh |

### Feed item display
```
 [I]  owner/repo  #42   Fix memory leak   alice     3d
 [PR] owner/repo  #55   Add retry logic   bob       1d  [draft]
```

`[I]` = issue, `[PR]` = pull request.  Merged / closed items appear dimmed.

---

## Notifications mode

```
dion-issues --notif [--all] [--repo OWNER/REPO] [--kind TYPE] [--reason REASON]
```

Shows GitHub notification threads for the authenticated user.
Defaults to **unread only**; `--all` includes read notifications.

### Notification filters (CLI flags)
| Flag | Purpose |
|------|---------|
| `--repo OWNER/REPO`    | Show only notifications from this repo (repeatable) |
| `--kind TYPE`          | Issue \| PullRequest \| Commit \| Release \| Discussion |
| `--reason REASON`      | mention, assign, review_requested, subscribed, … |
| `--all`                | Show read + unread (default: unread only) |
| `--refresh-interval N` | Auto-refresh every N seconds (default 120) |

### Notification keybindings
| Key | Action |
|-----|--------|
| `j` / `k` | Move |
| `Enter`   | Open issue / PR detail (if available) |
| `m`       | Mark selected notification as read |
| `M`       | Mark all visible as read |
| `r`       | Force refresh |
| `/`       | In-session text filter (ESC to clear) |
| `q`       | Quit |

### Notification item display
```
 ● [I]  org/repo              PR title goes here      mention   1h
 ○ [PR] org/other-repo        Fix the thing           review    3d
```

`●` = unread, `○` = read.

---

## Data at rest
- Cache: `~/.cache/gh-issues-tui/<sha16>.json` — JSON envelope with timestamp + payload.
- Drafts: `~/.local/share/gh-issues-tui/drafts.json` — JSON map of `"repo#N"` → draft.
- Both files are plain UTF-8 JSON; human-readable and easy to inspect or delete.

## Failure modes
- No network: serve cached data; show `[offline]` in status; block submit.
- Auth failure: exit with clear message directing user to `gh auth login`.
- Rate limit: surface the `gh` error message; do not crash.
- Corrupt cache/drafts file: delete and start fresh, log a warning to stderr.
