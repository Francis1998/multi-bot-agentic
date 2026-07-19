"""Tests for the deterministic regex extraction tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.regex_extract import RegexExtractTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the regex tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional ``pattern``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = RegexExtractTool().execute(ToolInvocation(tool_name="regex", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_regex_extracts_matches_with_groups() -> None:
    """A pattern with capture groups returns spans, matches, and groups as JSON."""

    ok, content, metadata = _run(text="id=42 id=7", pattern=r"id=(\d+)")

    assert ok is True
    payload = json.loads(content)
    assert payload["count"] == 2
    assert payload["matches"][0]["match"] == "id=42"
    assert payload["matches"][0]["groups"] == ["42"]
    assert payload["matches"][0]["start"] == 0
    assert metadata["count"] == 2


def test_regex_accepts_sentinel_split_in_text() -> None:
    """A single ``text`` split on ``<<<REGEX>>>`` supplies document and pattern."""

    ok, content, metadata = _run(text="alpha-123-beta<<<REGEX>>>[0-9]+")

    assert ok is True
    payload = json.loads(content)
    assert payload["count"] == 1
    assert payload["matches"][0]["match"] == "123"
    assert metadata["pattern"] == "[0-9]+"


def test_regex_rejects_invalid_pattern() -> None:
    """An uncompilable pattern is a structured failure."""

    ok, content, metadata = _run(text="hello", pattern="(")

    assert ok is False
    assert "invalid regex" in content
    assert metadata["pattern"] == "("


def test_regex_rejects_empty_document() -> None:
    """An empty document is a structured failure."""

    ok, content, _metadata = _run(text="", pattern="a+")

    assert ok is False
    assert "document is empty" in content


def test_regex_rejects_oversized_document() -> None:
    """A document above the char cap is a structured failure."""

    ok, content, metadata = _run(text="x" * 20_001, pattern="x")

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_regex_is_registered_in_default_tools() -> None:
    """The regex tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "regex" in tools
    assert tools["regex"].name == "regex"
    assert "regex" in SafetyPolicy().allowed_tools
