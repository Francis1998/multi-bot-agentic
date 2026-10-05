"""Unit tests for OrchestratorCascadeFailureAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.orchestrator_cascade_failure import OrchestratorCascadeFailureAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = OrchestratorCascadeFailureAdvisor().advise("s1", cascade_depth=1.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = OrchestratorCascadeFailureAdvisor().advise("s1", cascade_depth=3.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = OrchestratorCascadeFailureAdvisor().advise("s1", cascade_depth=6.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="cascade_depth"):
        OrchestratorCascadeFailureAdvisor().advise("s1", cascade_depth=-1.0)
