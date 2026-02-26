"""Unified feed model combining issues and pull requests.

A feed aggregates items from one or more repos, normalises them into a
consistent shape, and provides filtering / sorting helpers.

Public surface:
    FeedItem          — normalised issue or PR
    build_feed(raw_items, repo) — convert raw API dicts to FeedItems
    filter_feed(items, ...)     — filter by kind/label/author/state
    sort_feed(items)            — sort by updated_at descending
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FeedItem:
    """One entry in the combined issue + PR feed."""
    kind: Literal["issue", "pr"]
    repo: str
    number: int
    title: str
    state: str          # open / closed / merged
    author: str
    updated_at: str     # ISO 8601
    created_at: str     # ISO 8601
    labels: list[str]   # label name strings
    is_draft: bool      # draft PRs
    comment_count: int


def build_feed(raw: list[dict], repo: str) -> list["FeedItem"]:
    """Convert a list of raw API issue/PR dicts to FeedItems.

    Items are expected to already have a ``_kind`` = "pr" marker added by
    ``fetch_pull_requests()``, or no marker (treated as "issue").
    """
    items: list[FeedItem] = []
    for obj in raw:
        kind: Literal["issue", "pr"] = obj.get("_kind", "issue")
        # Issues that are PRs come back from the issues endpoint with a
        # pull_request sub-key.  We skip them here; fetch them via the
        # pulls endpoint instead to avoid duplicates.
        if kind == "issue" and obj.get("pull_request"):
            continue
        state = obj.get("state", "open")
        # GitHub marks merged PRs as "closed"; detect merge state.
        if kind == "pr" and obj.get("merged_at"):
            state = "merged"
        items.append(FeedItem(
            kind=kind,
            repo=repo,
            number=obj.get("number", 0),
            title=obj.get("title", "(no title)"),
            state=state,
            author=(obj.get("user") or {}).get("login", ""),
            updated_at=obj.get("updated_at", ""),
            created_at=obj.get("created_at", ""),
            labels=[lbl.get("name", "") for lbl in obj.get("labels", [])],
            is_draft=bool(obj.get("draft", False)),
            comment_count=obj.get("comments", 0),
        ))
    return items


def filter_feed(
    items: list[FeedItem],
    *,
    kind: str | None = None,        # "issue" | "pr" | None
    label: str | None = None,       # label name substring (case-insensitive)
    author: str | None = None,      # author login substring (case-insensitive)
    state: str | None = None,       # "open" | "closed" | "merged" | None
    search: str | None = None,      # substring match on title/number
) -> list[FeedItem]:
    """Return a subset of items matching all provided criteria."""
    result = items

    if kind:
        result = [i for i in result if i.kind == kind]

    if state:
        result = [i for i in result if i.state == state]

    if label:
        q = label.lower()
        result = [i for i in result if any(q in l.lower() for l in i.labels)]

    if author:
        q = author.lower()
        result = [i for i in result if q in i.author.lower()]

    if search:
        q = search.lower().lstrip("/")
        result = [
            i for i in result
            if q in i.title.lower()
            or q in str(i.number)
            or any(q in l.lower() for l in i.labels)
            or q in i.author.lower()
        ]

    return result


def sort_feed(items: list[FeedItem]) -> list[FeedItem]:
    """Sort items by updated_at descending (newest first)."""
    return sorted(items, key=lambda i: i.updated_at, reverse=True)
