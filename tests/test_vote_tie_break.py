"""Unit tests for VoteTieBreakPolicy."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.vote_tie_break import VoteTieBreakPolicy


def test_lexicographic_winner() -> None:
    """Lexicographic policy picks the first sorted option."""

    result = VoteTieBreakPolicy().resolve(
        "s1",
        tied_options=["beta", "alpha"],
        policy="lexicographic",
    )
    assert result.winner == "alpha"
    assert result.band == "resolved"
    assert result.requires_human_review is True


def test_escalate_leaves_winner_none() -> None:
    """Escalate policy requires human choice."""

    result = VoteTieBreakPolicy().resolve(
        "s1",
        tied_options=["a", "b"],
        policy="escalate",
    )
    assert result.winner is None
    assert result.band == "escalate"


def test_seeded_is_deterministic() -> None:
    """Seeded policy is stable for the same seed."""

    a = VoteTieBreakPolicy().resolve("s1", tied_options=["x", "y"], policy="seeded", seed="run-7")
    b = VoteTieBreakPolicy().resolve("s1", tied_options=["y", "x"], policy="seeded", seed="run-7")
    assert a.winner == b.winner


def test_invalid_raises() -> None:
    """Fewer than two options raises ValueError."""

    with pytest.raises(ValueError, match="tied_options"):
        VoteTieBreakPolicy().resolve("s1", tied_options=["only"])


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/vote_tie_break.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
