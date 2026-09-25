"""Unit tests for CriticVerdictDiversityGate."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.critic_verdict_diversity import CriticVerdictDiversityGate


def test_diverse() -> None:
    """Distinct verdicts are diverse."""

    status = CriticVerdictDiversityGate().check(
        "s1",
        ["accept", "revise", "reject"],
    )
    assert status.band == "diverse"
    assert status.unique_verdicts == 3


def test_echo_chamber() -> None:
    """Identical verdicts are echo_chamber."""

    status = CriticVerdictDiversityGate().check(
        "s1",
        ["accept", "ACCEPT", "accept"],
        min_diversity_ratio=0.5,
    )
    assert status.band == "echo_chamber"
    assert status.requires_human_review is True


def test_empty() -> None:
    """No verdicts is empty."""

    status = CriticVerdictDiversityGate().check("s1", [])
    assert status.band == "empty"


def test_invalid_session_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        CriticVerdictDiversityGate().check("  ", ["accept"])


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/critic_verdict_diversity.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
