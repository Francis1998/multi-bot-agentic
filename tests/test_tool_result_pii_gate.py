"""Unit tests for ToolResultPiiRedactionGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_pii_gate import ToolResultPiiRedactionGate


def test_clear_band() -> None:
    """No PII patterns is clear."""

    status = ToolResultPiiRedactionGate().check("search", result_text="ok")
    assert status.band == "clear"
    assert status.requires_human_review is True


def test_redact_band() -> None:
    """Single email match is redact."""

    status = ToolResultPiiRedactionGate().check("search", result_text="contact me@example.com please")
    assert status.band == "redact"
    assert "email" in status.matched_kinds


def test_block_band_ssn() -> None:
    """SSN match is block."""

    status = ToolResultPiiRedactionGate().check("search", result_text="ssn 123-45-6789")
    assert status.band == "block"


def test_empty_tool_raises() -> None:
    """Empty tool name raises ValueError."""

    with pytest.raises(ValueError, match="tool_name"):
        ToolResultPiiRedactionGate().check(" ", result_text="x")
