"""Tests for ToolCallIdempotencyCache."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_idempotency_cache import ToolCallIdempotencyCache


def test_put_get_replay_same_args() -> None:
    """put then get with identical tool+args returns the cached result."""

    cache = ToolCallIdempotencyCache()
    entry = cache.put(
        "search",
        {"q": "docs", "limit": 3},
        "hit:docs",
        cached_at_iso="2026-09-13T12:00:00+00:00",
    )
    assert entry.tool_name == "search"
    assert entry.args == {"q": "docs", "limit": 3}
    assert entry.result == "hit:docs"
    assert entry.cache_key
    assert entry.cached_at_iso == "2026-09-13T12:00:00+00:00"

    replay = cache.get("search", {"q": "docs", "limit": 3})
    assert replay is not None
    assert replay.cache_key == entry.cache_key
    assert replay.result == "hit:docs"


def test_canonical_arg_order_same_key() -> None:
    """Args with different key insertion order share one cache key."""

    cache = ToolCallIdempotencyCache()
    a = cache.put("echo", {"b": 2, "a": 1}, "ok")
    b = cache.get("echo", {"a": 1, "b": 2})
    assert b is not None
    assert a.cache_key == b.cache_key


def test_different_args_miss() -> None:
    """Different args for the same tool do not collide."""

    cache = ToolCallIdempotencyCache()
    cache.put("echo", {"x": 1}, "one")
    assert cache.get("echo", {"x": 2}) is None


def test_invalidate_removes_entry() -> None:
    """invalidate drops a previously cached entry."""

    cache = ToolCallIdempotencyCache()
    cache.put("t", {"k": "v"}, "r")
    assert cache.invalidate("t", {"k": "v"}) is True
    assert cache.get("t", {"k": "v"}) is None
    assert cache.invalidate("t", {"k": "v"}) is False


def test_args_copied_on_put() -> None:
    """Mutating caller args after put does not change the stored entry."""

    cache = ToolCallIdempotencyCache()
    args = {"path": "/tmp/x"}
    entry = cache.put("read", args, "content")
    args["path"] = "/tmp/y"
    assert entry.args["path"] == "/tmp/x"
    assert cache.get("read", {"path": "/tmp/x"}) is not None


def test_rejects_empty_tool_name() -> None:
    """Empty tool_name raises ValueError."""

    cache = ToolCallIdempotencyCache()
    with pytest.raises(ValueError, match="tool_name"):
        cache.put("  ", {}, "r")
    with pytest.raises(ValueError, match="tool_name"):
        cache.get("", {})
    with pytest.raises(ValueError, match="tool_name"):
        cache.invalidate(" ", {})


def test_rejects_non_mapping_args() -> None:
    """Non-mapping args raise TypeError."""

    cache = ToolCallIdempotencyCache()
    with pytest.raises(TypeError):
        cache.put("t", ["not", "map"], "r")  # type: ignore[arg-type]


def test_default_cached_at_iso() -> None:
    """Omitting cached_at_iso still yields a non-empty ISO-like stamp."""

    cache = ToolCallIdempotencyCache()
    entry = cache.put("t", {"a": 1}, "ok")
    assert "T" in entry.cached_at_iso
