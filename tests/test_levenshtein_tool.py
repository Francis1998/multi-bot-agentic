"""Tests for the levenshtein tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.levenshtein import LevenshteinTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the levenshtein tool."""

    result = LevenshteinTool().execute(ToolInvocation(tool_name="levenshtein", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_levenshtein_identical_strings_are_zero() -> None:
    """Identical strings have distance 0."""

    ok, content, metadata = _run(a="kitten", b="kitten")
    assert ok is True
    assert content == "0"
    assert metadata["distance"] == 0


def test_levenshtein_classic_kitten_sitting() -> None:
    """Classic kitten→sitting example is distance 3."""

    ok, content, metadata = _run(a="kitten", b="sitting")
    assert ok is True
    assert content == "3"
    assert metadata["distance"] == 3


def test_levenshtein_empty_against_nonempty() -> None:
    """Empty vs nonempty equals the nonempty length."""

    ok, content, metadata = _run(a="", b="abc")
    assert ok is True
    assert content == "3"
    assert metadata["distance"] == 3


def test_levenshtein_rejects_missing_args() -> None:
    """Missing a/b fails structurally."""

    ok, content, _metadata = _run(a="only-a")
    assert ok is False
    assert "missing required arguments" in content


def test_levenshtein_rejects_oversized_input() -> None:
    """Inputs over 2000 chars fail."""

    ok, content, metadata = _run(a="x" * 2001, b="y")
    assert ok is False
    assert "exceeds max" in content
    assert metadata["a_chars"] == 2001


def test_levenshtein_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "levenshtein" in tools
    assert tools["levenshtein"].name == "levenshtein"
    SafetyPolicy().validate_tool("levenshtein")
    assert "levenshtein" in SafetyPolicy().allowed_tools
