"""Tests for the text indent tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_indent import TextIndentTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_indent tool."""

    result = TextIndentTool().execute(ToolInvocation(tool_name="text_indent", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_indent_indents_non_empty_lines_by_two_spaces_by_default() -> None:
    """Non-empty lines gain two leading spaces; blank lines stay blank."""

    ok, content, metadata = _run(text="GPT-5.5\n\nClaude Sonnet 4.6\n")

    assert ok is True
    assert content == "  GPT-5.5\n\n  Claude Sonnet 4.6\n"
    assert metadata["spaces"] == 2
    assert metadata["skip_first"] is False
    assert metadata["input_chars"] == len("GPT-5.5\n\nClaude Sonnet 4.6\n")
    assert metadata["chars"] == len(content)


def test_text_indent_supports_custom_spaces_and_skip_first() -> None:
    """spaces and skip_first control indent width and first-line behavior."""

    ok, content, metadata = _run(
        text="Gemini 3.x\nKimi K2\n",
        spaces=4,
        skip_first=True,
    )

    assert ok is True
    assert content == "Gemini 3.x\n    Kimi K2\n"
    assert metadata["spaces"] == 4
    assert metadata["skip_first"] is True


def test_text_indent_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies spaces and optional skip_first."""

    ok, content, metadata = _run(text="a\nb<<<TEXT_INDENT>>>3:true")

    assert ok is True
    assert content == "a\n   b"
    assert metadata["spaces"] == 3
    assert metadata["skip_first"] is True


def test_text_indent_rejects_empty_oversized_and_invalid_options() -> None:
    """Empty, oversized, and invalid option inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_spaces, content_spaces, _m3 = _run(text="value", spaces=33)
    ok_flag, content_flag, _m4 = _run(text="value", skip_first="sometimes")
    ok_sentinel, content_sentinel, _m5 = _run(text="value<<<TEXT_INDENT>>>2<<<TEXT_INDENT>>>4")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_spaces is False and "spaces must be an integer" in content_spaces
    assert ok_flag is False and "skip_first must be a boolean" in content_flag
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_text_indent_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_indent" in tools
    assert tools["text_indent"].name == "text_indent"
    SafetyPolicy().validate_tool("text_indent")
    assert "text_indent" in SafetyPolicy().allowed_tools
