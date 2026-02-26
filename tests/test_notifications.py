"""Tests for notification data model and filtering."""

from gh_issues.notifications import NotifItem, build_notif_items, filter_notifs, _parse_number_from_url


# ------------------------------------------------------------------
# _parse_number_from_url
# ------------------------------------------------------------------

def test_parse_number_from_issue_url():
    url = "https://api.github.com/repos/owner/repo/issues/42"
    assert _parse_number_from_url(url) == 42


def test_parse_number_from_pr_url():
    url = "https://api.github.com/repos/owner/repo/pulls/7"
    assert _parse_number_from_url(url) == 7


def test_parse_number_returns_none_for_empty():
    assert _parse_number_from_url("") is None


def test_parse_number_returns_none_for_non_numeric():
    assert _parse_number_from_url("https://api.github.com/repos/owner/repo/issues/abc") is None


# ------------------------------------------------------------------
# build_notif_items
# ------------------------------------------------------------------

def _raw_notif(
    thread_id: str = "1",
    repo: str = "owner/repo",
    kind: str = "Issue",
    title: str = "Test issue",
    reason: str = "mention",
    unread: bool = True,
    updated: str = "2026-01-01T00:00:00Z",
    subject_url: str = "https://api.github.com/repos/owner/repo/issues/99",
) -> dict:
    return {
        "id": thread_id,
        "repository": {"full_name": repo},
        "subject": {"type": kind, "title": title, "url": subject_url},
        "reason": reason,
        "unread": unread,
        "updated_at": updated,
    }


def test_build_notif_items_parses_fields():
    items = build_notif_items([_raw_notif()])
    assert len(items) == 1
    item = items[0]
    assert item.thread_id == "1"
    assert item.repo == "owner/repo"
    assert item.kind == "Issue"
    assert item.title == "Test issue"
    assert item.reason == "mention"
    assert item.unread is True
    assert item.issue_number == 99


def test_build_notif_treats_pr_kind():
    raw = _raw_notif(
        kind="PullRequest",
        subject_url="https://api.github.com/repos/owner/repo/pulls/5",
    )
    items = build_notif_items([raw])
    assert items[0].kind == "PullRequest"
    assert items[0].issue_number == 5


def test_build_notif_empty_input():
    assert build_notif_items([]) == []


# ------------------------------------------------------------------
# filter_notifs
# ------------------------------------------------------------------

def _sample_notifs() -> list[NotifItem]:
    return build_notif_items([
        _raw_notif("1", repo="org/repo-a", kind="Issue", reason="mention", unread=True),
        _raw_notif("2", repo="org/repo-b", kind="PullRequest", reason="assign", unread=True),
        _raw_notif("3", repo="org/repo-a", kind="Issue", reason="subscribed", unread=False),
        _raw_notif("4", repo="org/repo-c", kind="Release", reason="subscribed", unread=True,
                   subject_url=""),
    ])


def test_filter_unread_only():
    items = filter_notifs(_sample_notifs(), unread_only=True)
    assert all(i.unread for i in items)
    assert len(items) == 3


def test_filter_by_repos():
    items = filter_notifs(_sample_notifs(), repos=["org/repo-a"])
    assert all(i.repo == "org/repo-a" for i in items)
    assert len(items) == 2


def test_filter_by_kind():
    items = filter_notifs(_sample_notifs(), kind="Issue")
    assert all(i.kind == "Issue" for i in items)
    assert len(items) == 2


def test_filter_by_reason():
    items = filter_notifs(_sample_notifs(), reason="mention")
    assert len(items) == 1
    assert items[0].thread_id == "1"


def test_filter_by_search_title():
    items = filter_notifs(_sample_notifs(), search="test issue")
    assert len(items) == 4  # all titles are "Test issue"


def test_filter_by_search_repo():
    items = filter_notifs(_sample_notifs(), search="repo-c")
    assert len(items) == 1
    assert items[0].thread_id == "4"


def test_filter_no_criteria_returns_all():
    original = _sample_notifs()
    assert len(filter_notifs(original)) == len(original)


def test_filter_combined_repo_and_kind():
    items = filter_notifs(
        _sample_notifs(),
        repos=["org/repo-a"],
        kind="Issue",
    )
    assert all(i.repo == "org/repo-a" and i.kind == "Issue" for i in items)
    assert len(items) == 2
