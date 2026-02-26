"""Tests for feed data model and filtering."""

from gh_issues.feed import FeedItem, build_feed, filter_feed, sort_feed


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_issue_raw(number: int = 1, title: str = "Fix bug",
                    state: str = "open", labels: list[str] | None = None,
                    author: str = "alice", updated: str = "2026-01-01T00:00:00Z"):
    raw = {
        "number": number,
        "title": title,
        "state": state,
        "user": {"login": author},
        "updated_at": updated,
        "created_at": updated,
        "labels": [{"name": l} for l in (labels or [])],
        "comments": 0,
    }
    return raw


def _make_pr_raw(number: int = 10, title: str = "Add feature",
                 state: str = "open", author: str = "bob",
                 draft: bool = False, merged_at: str | None = None,
                 updated: str = "2026-01-02T00:00:00Z"):
    raw = {
        "_kind": "pr",
        "number": number,
        "title": title,
        "state": state,
        "user": {"login": author},
        "updated_at": updated,
        "created_at": updated,
        "labels": [],
        "comments": 0,
        "draft": draft,
        "merged_at": merged_at,
    }
    return raw


# ------------------------------------------------------------------
# build_feed
# ------------------------------------------------------------------

def test_build_feed_returns_feed_items():
    items = build_feed([_make_issue_raw()], repo="org/repo")
    assert len(items) == 1
    assert items[0].kind == "issue"
    assert items[0].repo == "org/repo"
    assert items[0].number == 1


def test_build_feed_marks_pr_kind():
    items = build_feed([_make_pr_raw()], repo="org/repo")
    assert items[0].kind == "pr"


def test_build_feed_skips_issues_with_pull_request_key():
    """Issues endpoint returns PRs with a pull_request sub-key; they should be skipped."""
    raw = _make_issue_raw(number=5)
    raw["pull_request"] = {"url": "https://api.github.com/repos/org/repo/pulls/5"}
    items = build_feed([raw], repo="org/repo")
    assert items == []


def test_build_feed_sets_merged_state_for_merged_prs():
    raw = _make_pr_raw(state="closed", merged_at="2026-01-03T00:00:00Z")
    items = build_feed([raw], repo="org/repo")
    assert items[0].state == "merged"


def test_build_feed_extracts_labels():
    raw = _make_issue_raw(labels=["bug", "help wanted"])
    items = build_feed([raw], repo="org/repo")
    assert items[0].labels == ["bug", "help wanted"]


def test_build_feed_draft_pr():
    raw = _make_pr_raw(draft=True)
    items = build_feed([raw], repo="org/repo")
    assert items[0].is_draft is True


# ------------------------------------------------------------------
# filter_feed
# ------------------------------------------------------------------

def _sample_items() -> list[FeedItem]:
    return build_feed([
        _make_issue_raw(1, "Fix crash", labels=["bug"], author="alice"),
        _make_issue_raw(2, "Add docs", labels=["docs"], author="bob"),
        _make_pr_raw(10, "Improve perf", author="alice"),
        _make_pr_raw(11, "Refactor DB", author="carol"),
    ], repo="org/repo")


def test_filter_by_kind_issue():
    items = filter_feed(_sample_items(), kind="issue")
    assert all(i.kind == "issue" for i in items)
    assert len(items) == 2


def test_filter_by_kind_pr():
    items = filter_feed(_sample_items(), kind="pr")
    assert all(i.kind == "pr" for i in items)
    assert len(items) == 2


def test_filter_by_label():
    items = filter_feed(_sample_items(), label="bug")
    assert len(items) == 1
    assert items[0].number == 1


def test_filter_by_label_case_insensitive():
    items = filter_feed(_sample_items(), label="BUG")
    assert len(items) == 1


def test_filter_by_author():
    items = filter_feed(_sample_items(), author="alice")
    assert len(items) == 2
    assert all(i.author == "alice" for i in items)


def test_filter_by_search_title():
    items = filter_feed(_sample_items(), search="crash")
    assert len(items) == 1
    assert items[0].number == 1


def test_filter_by_search_number():
    items = filter_feed(_sample_items(), search="10")
    assert len(items) == 1
    assert items[0].number == 10


def test_filter_combined_kind_and_label():
    items = filter_feed(_sample_items(), kind="issue", label="docs")
    assert len(items) == 1
    assert items[0].number == 2


def test_filter_no_criteria_returns_all():
    original = _sample_items()
    assert len(filter_feed(original)) == len(original)


# ------------------------------------------------------------------
# sort_feed
# ------------------------------------------------------------------

def test_sort_feed_newest_first():
    items = build_feed([
        _make_issue_raw(1, updated="2026-01-01T00:00:00Z"),
        _make_issue_raw(2, updated="2026-01-03T00:00:00Z"),
        _make_issue_raw(3, updated="2026-01-02T00:00:00Z"),
    ], repo="org/repo")
    sorted_items = sort_feed(items)
    assert sorted_items[0].number == 2
    assert sorted_items[1].number == 3
    assert sorted_items[2].number == 1
