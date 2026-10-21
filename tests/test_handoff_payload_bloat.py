"""Tests for HandoffPayloadBloatAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.handoff_payload_bloat import HandoffPayloadBloatAdvisor


def test_ok_band() -> None:
    """Below soft is ok."""

    status = HandoffPayloadBloatAdvisor().advise("s1", payload_bloat_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard is elevated."""

    status = HandoffPayloadBloatAdvisor().advise("s1", payload_bloat_ratio=0.4)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard is blocked."""

    status = HandoffPayloadBloatAdvisor().advise("s1", payload_bloat_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Blank session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        HandoffPayloadBloatAdvisor().advise(" ", payload_bloat_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="payload_bloat_ratio"):
        HandoffPayloadBloatAdvisor().advise("s1", payload_bloat_ratio=-0.1)
