"""Tests for safety controls."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.safety import SafetyError, SafetyPolicy


def test_safety_rejects_oversized_goal() -> None:
    """Prompt bounds prevent unbounded scope."""

    policy = SafetyPolicy(max_prompt_chars=4)

    with pytest.raises(SafetyError):
        policy.validate_goal("too long")


def test_safety_blocks_unallowed_tool() -> None:
    """Tool allowlists block unknown tools."""

    policy = SafetyPolicy(allowed_tools=frozenset({"echo"}))

    with pytest.raises(SafetyError):
        policy.validate_tool("shell")


def test_safety_detects_cancellation_file(tmp_path: Path) -> None:
    """Cancellation files stop runs before the next action."""

    cancel_file = tmp_path / "cancel"
    policy = SafetyPolicy(cancellation_file=cancel_file)
    cancel_file.write_text("stop", encoding="utf-8")

    assert policy.is_cancelled() is True
