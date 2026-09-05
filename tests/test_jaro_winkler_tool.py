"""Tests for the jaro_winkler tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.jaro_winkler import JaroWinklerTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the jaro_winkler tool."""

    result = JaroWinklerTool().execute(ToolInvocation(tool_name="jaro_winkler", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_jaro_winkler_identical_strings_are_one() -> None:
    """Identical strings have similarity 1."""

    ok, content, metadata = _run(a="martha", b="martha")
    assert ok is True
    assert content == "1"
    assert metadata["similarity"] == 1.0


def test_jaro_winkler_classic_martha_marhta() -> None:
    """Classic martha/marhta example is ~0.961."""

    ok, content, metadata = _run(a="martha", b="marhta")
    assert ok is True
    score = float(metadata["similarity"])  # type: ignore[arg-type]
    assert 0.96 < score < 0.97
    assert abs(float(content) - score) < 1e-6


def test_jaro_winkler_completely_different_is_zero() -> None:
    """Unrelated strings score 0."""

    ok, content, metadata = _run(a="abc", b="xyz")
    assert ok is True
    assert content == "0"
    assert metadata["similarity"] == 0.0


def test_jaro_winkler_empty_against_nonempty() -> None:
    """Empty vs nonempty is 0."""

    ok, content, metadata = _run(a="", b="abc")
    assert ok is True
    assert content == "0"
    assert metadata["similarity"] == 0.0


def test_jaro_winkler_rejects_missing_and_oversized() -> None:
    """Missing a/b and oversized inputs fail."""

    ok, content, _metadata = _run(a="only-a")
    assert ok is False
    assert "missing required arguments" in content
    ok_big, content_big, metadata_big = _run(a="x" * 2001, b="y")
    assert ok_big is False
    assert "exceeds max" in content_big
    assert metadata_big["a_chars"] == 2001


def test_jaro_winkler_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "jaro_winkler" in tools
    assert tools["jaro_winkler"].name == "jaro_winkler"
    SafetyPolicy().validate_tool("jaro_winkler")
    assert "jaro_winkler" in SafetyPolicy().allowed_tools
