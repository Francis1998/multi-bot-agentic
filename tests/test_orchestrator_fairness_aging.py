"""Unit tests for OrchestratorFairnessAgingAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.orchestrator_fairness_aging import OrchestratorFairnessAgingAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = OrchestratorFairnessAgingAdvisor().check("s1", wait_age_seconds=10.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = OrchestratorFairnessAgingAdvisor().check("s1", wait_age_seconds=60.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = OrchestratorFairnessAgingAdvisor().check("s1", wait_age_seconds=180.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="wait_age_seconds"):
        OrchestratorFairnessAgingAdvisor().check("s1", wait_age_seconds=-1.0)
