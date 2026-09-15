"""Tests for ToolCallLatencyTracker."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_latency import ToolCallLatencyTracker


def test_record_updates_sample_count_and_last() -> None:
    """record appends samples and exposes last_ms."""

    tracker = ToolCallLatencyTracker()
    s1 = tracker.record("search", 10.0)
    assert s1.sample_count == 1
    assert s1.last_ms == 10.0
    s2 = tracker.record("search", 30.0)
    assert s2.sample_count == 2
    assert s2.last_ms == 30.0


def test_p50_and_p95_on_known_samples() -> None:
    """p50/p95 use nearest-rank on sorted samples."""

    tracker = ToolCallLatencyTracker()
    for ms in (10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0):
        tracker.record("calc", ms)
    stats = tracker.stats("calc")
    assert stats.sample_count == 10
    assert stats.p50_ms == 50.0
    assert stats.p95_ms == 100.0


def test_stats_empty_tool_returns_nones() -> None:
    """Unseen tools report zero samples and None percentiles."""

    tracker = ToolCallLatencyTracker()
    stats = tracker.stats("missing")
    assert stats.sample_count == 0
    assert stats.p50_ms is None
    assert stats.p95_ms is None
    assert stats.last_ms is None


def test_tools_are_isolated() -> None:
    """Different tools keep independent sample buffers."""

    tracker = ToolCallLatencyTracker()
    tracker.record("a", 5.0)
    tracker.record("a", 15.0)
    tracker.record("b", 100.0)
    assert tracker.stats("a").sample_count == 2
    assert tracker.stats("b").sample_count == 1
    assert tracker.stats("b").last_ms == 100.0


def test_ring_buffer_respects_max_samples() -> None:
    """Oldest samples drop when max_samples_per_tool is exceeded."""

    tracker = ToolCallLatencyTracker(max_samples_per_tool=3)
    for ms in (1.0, 2.0, 3.0, 4.0):
        tracker.record("t", ms)
    stats = tracker.stats("t")
    assert stats.sample_count == 3
    assert stats.last_ms == 4.0
    # Remaining samples are 2, 3, 4 → p50 nearest-rank is 3
    assert stats.p50_ms == 3.0


def test_reset_clears_samples() -> None:
    """reset drops samples so the tool can be tracked fresh."""

    tracker = ToolCallLatencyTracker()
    tracker.record("t", 12.0)
    assert tracker.reset("t") is True
    assert tracker.stats("t").sample_count == 0
    assert tracker.reset("t") is False


def test_constructor_rejects_bad_bounds() -> None:
    """Non-positive max_samples_per_tool raises ValueError."""

    with pytest.raises(ValueError, match="max_samples_per_tool"):
        ToolCallLatencyTracker(max_samples_per_tool=0)


def test_rejects_empty_tool_and_negative_latency() -> None:
    """Empty tool_name or negative latency raises ValueError."""

    tracker = ToolCallLatencyTracker()
    with pytest.raises(ValueError, match="tool_name"):
        tracker.record("  ", 1.0)
    with pytest.raises(ValueError, match="latency_ms"):
        tracker.record("t", -0.1)
    with pytest.raises(ValueError, match="tool_name"):
        tracker.stats("")
    with pytest.raises(ValueError, match="tool_name"):
        tracker.reset(" ")
