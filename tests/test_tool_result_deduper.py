"""Tests for ToolResultFingerprintDeduper."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_deduper import ToolResultFingerprintDeduper


def test_first_accepts_second_drops() -> None:
    """First payload accepted; identical second marked duplicate and dropped."""

    deduper = ToolResultFingerprintDeduper(drop_duplicates=True)
    first = deduper.observe("s1", {"ok": True, "n": 1})
    second = deduper.observe("s1", {"ok": True, "n": 1})
    assert first.accepted is True
    assert first.is_duplicate is False
    assert second.is_duplicate is True
    assert second.accepted is False
    assert second.fingerprint == first.fingerprint
    assert second.seen_count == 2


def test_flag_only_mode_still_accepts() -> None:
    """When drop_duplicates=False, duplicates remain accepted."""

    deduper = ToolResultFingerprintDeduper(drop_duplicates=False)
    deduper.observe("s1", "same")
    again = deduper.observe("s1", "same")
    assert again.is_duplicate is True
    assert again.accepted is True


def test_sessions_isolated() -> None:
    """Fingerprints do not leak across sessions."""

    deduper = ToolResultFingerprintDeduper()
    deduper.observe("s1", "payload")
    other = deduper.observe("s2", "payload")
    assert other.is_duplicate is False
    assert other.accepted is True


def test_empty_session_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        ToolResultFingerprintDeduper().observe(" ", {"a": 1})
