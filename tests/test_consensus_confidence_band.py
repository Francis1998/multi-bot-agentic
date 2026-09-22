"""Unit tests for ConsensusConfidenceBandAdvisor."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.consensus_confidence_band import ConsensusConfidenceBandAdvisor


def test_unanimous() -> None:
    """Share 1.0 is unanimous."""

    band = ConsensusConfidenceBandAdvisor().advise("s1", vote_share=1.0)
    assert band.band == "unanimous"
    assert band.requires_human_review is True


def test_high_medium_low() -> None:
    """Thresholds map to high/medium/low."""

    advisor = ConsensusConfidenceBandAdvisor()
    assert advisor.advise("s", vote_share=0.8).band == "high"
    assert advisor.advise("s", vote_share=0.6).band == "medium"
    assert advisor.advise("s", vote_share=0.4).band == "low"


def test_invalid_share_raises() -> None:
    """Out-of-range vote_share raises ValueError."""

    with pytest.raises(ValueError, match="vote_share"):
        ConsensusConfidenceBandAdvisor().advise("s", vote_share=1.5)


def test_empty_session_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        ConsensusConfidenceBandAdvisor().advise("  ", vote_share=0.9)


def test_module_has_no_httpx_import() -> None:
    """Feature module must not import httpx."""

    source = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/consensus_confidence_band.py"
    assert "httpx" not in source.read_text(encoding="utf-8")
