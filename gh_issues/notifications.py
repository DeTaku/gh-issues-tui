"""Notification data model and filtering helpers.

GitHub's /notifications endpoint returns thread objects.  This module
normalises them into NotifItem dataclasses and provides filtering.

Reason values from the API:
    assign, author, comment, invitation, manual, mention,
    review_requested, security_alert, state_change, subscribed,
    team_mention, your_activity

Public surface:
    NotifItem                   — one notification thread
    build_notif_items(raw)      — parse raw API list
    filter_notifs(items, ...)   — filter by repo/kind/reason/text
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class NotifItem:
    thread_id: str
    repo: str           # "owner/repo"
    kind: str           # Issue | PullRequest | Commit | Release | Discussion
    title: str
    reason: str         # mention | assign | subscribed | review_requested | …
    unread: bool
    updated_at: str     # ISO 8601
    subject_url: str    # API URL to the underlying resource (may be empty)
    issue_number: int | None  # parsed from subject_url when available


def build_notif_items(raw: list[dict]) -> list[NotifItem]:
    """Convert raw /notifications API objects into NotifItems."""
    items: list[NotifItem] = []
    for obj in raw:
        subject = obj.get("subject") or {}
        repo_obj = obj.get("repository") or {}
        subject_url = subject.get("url") or ""
        items.append(NotifItem(
            thread_id=str(obj.get("id", "")),
            repo=repo_obj.get("full_name", ""),
            kind=subject.get("type", ""),
            title=subject.get("title", ""),
            reason=obj.get("reason", ""),
            unread=bool(obj.get("unread", False)),
            updated_at=obj.get("updated_at", ""),
            subject_url=subject_url,
            issue_number=_parse_number_from_url(subject_url),
        ))
    return items


def filter_notifs(
    items: list[NotifItem],
    *,
    repos: list[str] | None = None,     # exact "owner/repo" strings
    kind: str | None = None,            # Issue | PullRequest | etc. (case-insensitive)
    reason: str | None = None,          # mention | assign | … (case-insensitive)
    label: str | None = None,           # not available in notification data; ignored
    search: str | None = None,          # substring on title or repo
    unread_only: bool = False,
) -> list[NotifItem]:
    """Return a subset of items matching all provided criteria."""
    result = items

    if unread_only:
        result = [i for i in result if i.unread]

    if repos:
        repo_set = {r.lower() for r in repos}
        result = [i for i in result if i.repo.lower() in repo_set]

    if kind:
        q = kind.lower()
        result = [i for i in result if i.kind.lower() == q]

    if reason:
        q = reason.lower()
        result = [i for i in result if i.reason.lower() == q]

    if search:
        q = search.lower().lstrip("/")
        result = [
            i for i in result
            if q in i.title.lower() or q in i.repo.lower() or q in i.reason.lower()
        ]

    return result


def _parse_number_from_url(url: str) -> int | None:
    """Extract the trailing numeric ID from a GitHub API resource URL.

    e.g. "https://api.github.com/repos/torvalds/linux/issues/1234" → 1234
    """
    if not url:
        return None
    parts = url.rstrip("/").rsplit("/", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return None
