"""Unit tests for ToolResultPoisoningGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_poisoning import ToolResultPoisoningGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = ToolResultPoisoningGuard().check("s1", poison_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = ToolResultPoisoningGuard().check("s1", poison_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = ToolResultPoisoningGuard().check("s1", poison_score=0.9)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="poison_score"):
        ToolResultPoisoningGuard().check("s1", poison_score=-1.0)
