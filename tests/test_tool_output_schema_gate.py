"""Unit tests for ToolOutputSchemaGate."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.tool_output_schema_gate import ToolOutputSchemaGate


def test_pass() -> None:
    """All required keys present is pass."""

    verdict = ToolOutputSchemaGate().check(
        "search",
        {"query": "q", "hits": []},
        required_keys=("query", "hits"),
    )
    assert verdict.band == "pass"
    assert verdict.missing_keys == ()
    assert verdict.requires_human_review is True


def test_fail_missing() -> None:
    """Missing keys yield fail."""

    verdict = ToolOutputSchemaGate().check(
        "search",
        {"query": "q"},
        required_keys=("query", "hits"),
    )
    assert verdict.band == "fail"
    assert verdict.missing_keys == ("hits",)


def test_invalid_raises() -> None:
    """Empty required_keys raises ValueError."""

    with pytest.raises(ValueError, match="required_keys"):
        ToolOutputSchemaGate().check("t", {"a": 1}, required_keys=("  ",))


def test_no_httpx_import() -> None:
    """Module source must not import httpx."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/tool_output_schema_gate.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
