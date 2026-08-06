"""Tests for the bounded regex replace tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.regex_replace import RegexReplaceTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the regex_replace tool with the given arguments."""

    result = RegexReplaceTool().execute(ToolInvocation(tool_name="regex_replace", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_regex_replace_substitutes_matches() -> None:
    """Basic find/replace rewrites matching substrings."""

    ok, content, metadata = _run(text="foo bar foo", pattern="foo", repl="baz")

    assert ok is True
    assert content == "baz bar baz"
    assert cast(int, metadata["replacements"]) == 2


def test_regex_replace_respects_count() -> None:
    """count limits the number of replacements."""

    ok, content, metadata = _run(text="a a a", pattern="a", repl="b", count=2)

    assert ok is True
    assert content == "b b a"
    assert cast(int, metadata["replacements"]) == 2


def test_regex_replace_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="", pattern="a", repl="b")

    assert ok is False
    assert "empty" in content


def test_regex_replace_rejects_oversized_pattern() -> None:
    """Patterns longer than the bound are refused."""

    ok, content, metadata = _run(text="abc", pattern="a" * 201, repl="b")

    assert ok is False
    assert "max_chars" in content
    assert cast(int, metadata["chars"]) == 201


def test_regex_replace_rejects_nested_quantifiers() -> None:
    """Classic ReDoS nested-quantifier shapes are refused."""

    ok, content, metadata = _run(text="aaaa", pattern=r"(a+)+", repl="x")

    assert ok is False
    assert "nested quantifiers" in content
    assert metadata["pattern"] == r"(a+)+"


def test_regex_replace_rejects_invalid_regex() -> None:
    """Invalid patterns fail closed."""

    ok, content, _metadata = _run(text="abc", pattern="(", repl="x")

    assert ok is False
    assert "invalid regex" in content


def test_regex_replace_is_registered_in_default_tools(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "regex_replace" in tools
    assert tools["regex_replace"].name == "regex_replace"
    SafetyPolicy().validate_tool("regex_replace")
    assert "regex_replace" in SafetyPolicy().allowed_tools
