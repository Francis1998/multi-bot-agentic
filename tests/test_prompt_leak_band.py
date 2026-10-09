"""Unit tests for PromptLeakBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.prompt_leak_band import PromptLeakBandAdvisor


def test_ok() -> None:
    """Band ok."""

    status = PromptLeakBandAdvisor().check("s1", leak_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = PromptLeakBandAdvisor().check("s1", leak_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = PromptLeakBandAdvisor().check("s1", leak_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="leak_score"):
        PromptLeakBandAdvisor().check("s1", leak_score=-1.0)
