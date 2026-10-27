"""Unit tests for ToolSandboxEscapeAttemptBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_escape_attempt_band import ToolSandboxEscapeAttemptBandAdvisor


def test_ok_band() -> None:
    """Below soft limit -> ok."""

    status = ToolSandboxEscapeAttemptBandAdvisor().advise("s1", attempt_ratio=0.0250)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard -> elevated."""

    status = ToolSandboxEscapeAttemptBandAdvisor().advise("s1", attempt_ratio=0.1250)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard -> blocked."""

    status = ToolSandboxEscapeAttemptBandAdvisor().advise("s1", attempt_ratio=0.4000)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        ToolSandboxEscapeAttemptBandAdvisor().advise("  ", attempt_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="attempt_ratio"):
        ToolSandboxEscapeAttemptBandAdvisor().advise("s1", attempt_ratio=-0.1)
