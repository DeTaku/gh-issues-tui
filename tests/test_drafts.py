"""Tests for draft comment persistence."""

from pathlib import Path

import pytest

from gh_issues.drafts import DraftStore


@pytest.fixture
def store(tmp_path: Path) -> DraftStore:
    return DraftStore(tmp_path / "drafts.json")


# ------------------------------------------------------------------
# has_draft
# ------------------------------------------------------------------

def test_has_draft_false_when_empty(store: DraftStore) -> None:
    assert store.has_draft("owner/repo", 1) is False


def test_has_draft_false_for_blank_text(store: DraftStore) -> None:
    store.save("owner/repo", 1, "   ")
    assert store.has_draft("owner/repo", 1) is False


def test_has_draft_true_after_save(store: DraftStore) -> None:
    store.save("owner/repo", 42, "My draft comment")
    assert store.has_draft("owner/repo", 42) is True


# ------------------------------------------------------------------
# load / save round-trip
# ------------------------------------------------------------------

def test_load_returns_none_when_no_draft(store: DraftStore) -> None:
    assert store.load("owner/repo", 99) is None


def test_load_returns_saved_text(store: DraftStore) -> None:
    store.save("owner/repo", 7, "Hello, world!")
    assert store.load("owner/repo", 7) == "Hello, world!"


def test_save_overwrites_previous_draft(store: DraftStore) -> None:
    store.save("owner/repo", 1, "first")
    store.save("owner/repo", 1, "second")
    assert store.load("owner/repo", 1) == "second"


def test_drafts_are_isolated_by_repo(store: DraftStore) -> None:
    store.save("owner/repo-a", 1, "draft A")
    store.save("owner/repo-b", 1, "draft B")
    assert store.load("owner/repo-a", 1) == "draft A"
    assert store.load("owner/repo-b", 1) == "draft B"


def test_drafts_are_isolated_by_issue_number(store: DraftStore) -> None:
    store.save("owner/repo", 1, "draft one")
    store.save("owner/repo", 2, "draft two")
    assert store.load("owner/repo", 1) == "draft one"
    assert store.load("owner/repo", 2) == "draft two"


# ------------------------------------------------------------------
# discard
# ------------------------------------------------------------------

def test_discard_removes_draft(store: DraftStore) -> None:
    store.save("owner/repo", 5, "to be removed")
    store.discard("owner/repo", 5)
    assert store.load("owner/repo", 5) is None


def test_discard_missing_draft_is_noop(store: DraftStore) -> None:
    store.discard("owner/repo", 999)  # must not raise


def test_discard_does_not_affect_other_drafts(store: DraftStore) -> None:
    store.save("owner/repo", 1, "keep me")
    store.save("owner/repo", 2, "discard me")
    store.discard("owner/repo", 2)
    assert store.load("owner/repo", 1) == "keep me"
    assert store.load("owner/repo", 2) is None


# ------------------------------------------------------------------
# saved_at
# ------------------------------------------------------------------

def test_saved_at_returns_iso_string(store: DraftStore) -> None:
    store.save("owner/repo", 10, "text")
    ts = store.saved_at("owner/repo", 10)
    assert ts is not None
    assert "T" in ts  # ISO 8601 format


def test_saved_at_returns_none_for_missing(store: DraftStore) -> None:
    assert store.saved_at("owner/repo", 404) is None


# ------------------------------------------------------------------
# Persistence across instances
# ------------------------------------------------------------------

def test_drafts_persist_across_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    DraftStore(path).save("owner/repo", 3, "persisted")
    assert DraftStore(path).load("owner/repo", 3) == "persisted"


# ------------------------------------------------------------------
# Corruption handling
# ------------------------------------------------------------------

def test_corrupt_store_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    path.write_text("{not valid json}", encoding="utf-8")
    store = DraftStore(path)
    assert store.load("owner/repo", 1) is None
    assert store.has_draft("owner/repo", 1) is False
