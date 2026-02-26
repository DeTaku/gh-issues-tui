"""GitHub API access via the gh CLI.

All network I/O goes through `gh api` so authentication, token refresh,
and rate-limit headers are handled by the gh tool itself.
Only JSON output is parsed; no human-formatted text is consumed.

Public surface:
    check_auth()              — raise GhApiError if not logged in
    fetch_user_repos(limit)   — list repos the authenticated user owns/has access to
    fetch_issues(repo, state) — list issues
    fetch_issue(repo, number) — single issue
    fetch_comments(repo, number) — comments for an issue
    post_comment(repo, number, body) — create a comment
"""

import json
import subprocess
from typing import Any


class GhApiError(Exception):
    """Raised when a gh CLI call fails or returns unexpected output."""


def check_auth() -> None:
    """Raise GhApiError if the user has not authenticated with gh."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GhApiError(
            "Not authenticated with GitHub.\n"
            "Run:  gh auth login\n"
            f"Details: {result.stderr.strip()}"
        )


def fetch_user_repos(limit: int = 200) -> list[str]:
    """Return a list of 'owner/repo' strings for the authenticated user.

    Includes repos the user owns and repos they are a member of, ordered
    by most recently pushed.  Pass limit=-1 to fetch up to 1000.
    """
    safe_limit = min(max(1, limit), 1000)
    raw = _run_gh([
        "repo", "list",
        "--limit", str(safe_limit),
        "--json", "nameWithOwner",
    ])
    items: list[dict] = json.loads(raw) if raw.strip() else []
    return [item["nameWithOwner"] for item in items]


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout. Raise GhApiError on failure."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or f"gh exited with code {result.returncode}"
        raise GhApiError(msg)
    return result.stdout


def _parse_ndjson(text: str) -> list[Any]:
    """Parse output where each non-empty line is a JSON object/array."""
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def fetch_issues(repo: str, state: str = "open") -> list[dict]:
    """Return all issues for repo filtered by state (open / closed / all).

    Pull requests are excluded; only true issues are returned.
    Uses --paginate so all pages are fetched in a single call.
    """
    stdout = _run_gh([
        "gh", "api",
        f"repos/{repo}/issues",
        "--method", "GET",
        "--paginate",
        "--jq", ".[] | select(.pull_request == null)",
        "-F", f"state={state}",
        "-F", "per_page=100",
    ])
    if not stdout.strip():
        return []
    return _parse_ndjson(stdout)


def fetch_issue(repo: str, number: int) -> dict:
    """Return a single issue by number."""
    stdout = _run_gh(["gh", "api", f"repos/{repo}/issues/{number}"])
    return json.loads(stdout)


def fetch_comments(repo: str, number: int) -> list[dict]:
    """Return all comments for an issue in chronological order."""
    stdout = _run_gh([
        "gh", "api",
        f"repos/{repo}/issues/{number}/comments",
        "--paginate",
        "--jq", ".[]",
    ])
    if not stdout.strip():
        return []
    return _parse_ndjson(stdout)


def post_comment(repo: str, number: int, body: str) -> dict:
    """Post a comment on an issue and return the created comment object."""
    stdout = _run_gh([
        "gh", "api",
        f"repos/{repo}/issues/{number}/comments",
        "--method", "POST",
        "-f", f"body={body}",
    ])
    return json.loads(stdout)


def fetch_pull_requests(repo: str, state: str = "open") -> list[dict]:
    """Return all pull requests for repo filtered by state (open / closed / all).

    Each returned object has a ``_kind`` key set to ``"pr"`` for uniform
    handling alongside issues.
    """
    stdout = _run_gh([
        "gh", "api",
        f"repos/{repo}/pulls",
        "--method", "GET",
        "--paginate",
        "--jq", ".[]",
        "-F", f"state={state}",
        "-F", "per_page=100",
    ])
    if not stdout.strip():
        return []
    prs = _parse_ndjson(stdout)
    for pr in prs:
        pr["_kind"] = "pr"
    return prs


def fetch_notifications(
    all_notifs: bool = False,
    participating: bool = False,
) -> list[dict]:
    """Return notifications for the authenticated user.

    By default only unread notifications are returned.
    Pass all_notifs=True to include read notifications as well.
    """
    args = [
        "gh", "api", "notifications",
        "--method", "GET",
        "--paginate",
        "--jq", ".[]",
    ]
    if all_notifs:
        args += ["-F", "all=true"]
    if participating:
        args += ["-F", "participating=true"]
    stdout = _run_gh(args)
    if not stdout.strip():
        return []
    return _parse_ndjson(stdout)


def mark_notification_read(thread_id: str) -> None:
    """Mark a notification thread as read."""
    _run_gh([
        "gh", "api", f"notifications/threads/{thread_id}",
        "--method", "PATCH",
    ])
