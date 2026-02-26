"""Tests for the TTL disk cache."""

import json
import time
from pathlib import Path

import pytest

from gh_issues.cache import Cache


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache(tmp_path / "cache", ttl_seconds=60)


# ------------------------------------------------------------------
# Basic get / set
# ------------------------------------------------------------------

def test_get_returns_none_when_empty(cache: Cache) -> None:
    assert cache.get("missing-key") is None


def test_set_then_get_returns_data(cache: Cache) -> None:
    cache.set("k", {"hello": "world"})
    assert cache.get("k") == {"hello": "world"}


def test_set_then_get_works_for_lists(cache: Cache) -> None:
    data = [{"number": 1, "title": "Fix bug"}]
    cache.set("issues:org/repo:open", data)
    assert cache.get("issues:org/repo:open") == data


# ------------------------------------------------------------------
# TTL expiry
# ------------------------------------------------------------------

def test_expired_entry_returns_none(tmp_path: Path) -> None:
    short_cache = Cache(tmp_path / "short", ttl_seconds=1)
    short_cache.set("key", "value")
    assert short_cache.get("key") == "value"

    # Manually backdate the fetched_at timestamp to force expiry.
    path = short_cache._key_to_path("key")
    envelope = json.loads(path.read_text())
    envelope["fetched_at"] -= 10  # 10 seconds in the past
    path.write_text(json.dumps(envelope))

    assert short_cache.get("key") is None


def test_fresh_entry_is_returned(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "ttl", ttl_seconds=300)
    cache.set("k", 42)
    assert cache.get("k") == 42


# ------------------------------------------------------------------
# Invalidation
# ------------------------------------------------------------------

def test_invalidate_removes_entry(cache: Cache) -> None:
    cache.set("k", "v")
    cache.invalidate("k")
    assert cache.get("k") is None


def test_invalidate_missing_key_is_noop(cache: Cache) -> None:
    cache.invalidate("never-existed")  # must not raise


def test_invalidate_all_clears_everything(cache: Cache) -> None:
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate_all()
    assert cache.get("a") is None
    assert cache.get("b") is None


# ------------------------------------------------------------------
# Corruption handling
# ------------------------------------------------------------------

def test_corrupt_file_treated_as_cache_miss(cache: Cache) -> None:
    cache.set("k", "v")
    path = cache._key_to_path("k")
    path.write_text("not valid json", encoding="utf-8")
    assert cache.get("k") is None


def test_corrupt_file_is_deleted_after_miss(cache: Cache) -> None:
    cache.set("k", "v")
    path = cache._key_to_path("k")
    path.write_text("{bad", encoding="utf-8")
    cache.get("k")
    assert not path.exists()


# ------------------------------------------------------------------
# age_seconds
# ------------------------------------------------------------------

def test_age_seconds_returns_none_for_missing_key(cache: Cache) -> None:
    assert cache.age_seconds("missing") is None


def test_age_seconds_is_positive(cache: Cache) -> None:
    cache.set("k", "v")
    age = cache.age_seconds("k")
    assert age is not None
    assert 0 <= age < 5  # should be very fresh
