"""Tests for BotRoleConflictDetector."""

from __future__ import annotations

import pytest

from multi_bot_agentic.bot_role_conflict import BotRoleConflictDetector


def test_single_claim_ok() -> None:
    """One claimant is conflict-free."""

    det = BotRoleConflictDetector(mode="hard")
    report = det.claim("s1", "bot-a", "critic")
    assert report.conflict is False
    assert report.allowed is True
    assert report.claimants == ("bot-a",)


def test_hard_mode_blocks_second_claimant() -> None:
    """Hard mode rejects a second claimant for the same role."""

    det = BotRoleConflictDetector(mode="hard")
    det.claim("s1", "bot-a", "critic")
    report = det.claim("s1", "bot-b", "critic")
    assert report.conflict is True
    assert report.allowed is False
    assert set(report.claimants) == {"bot-a", "bot-b"}


def test_advisory_mode_allows_conflict() -> None:
    """Advisory mode flags conflict but keeps allowed=True."""

    det = BotRoleConflictDetector(mode="advisory")
    det.claim("s1", "bot-a", "planner")
    report = det.claim("s1", "bot-b", "planner")
    assert report.conflict is True
    assert report.allowed is True


def test_sessions_isolated() -> None:
    """Claims do not leak across sessions."""

    det = BotRoleConflictDetector(mode="hard")
    det.claim("s1", "bot-a", "critic")
    report = det.claim("s2", "bot-b", "critic")
    assert report.conflict is False


def test_empty_ids_raise() -> None:
    """Empty identifiers raise ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        BotRoleConflictDetector().claim(" ", "bot", "role")
    with pytest.raises(ValueError, match="mode"):
        BotRoleConflictDetector(mode="weird")
