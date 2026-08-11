"""Tests for the text dedenting tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_dedent import TextDedentTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_dedent tool."""

    result = TextDedentTool().execute(ToolInvocation(tool_name="text_dedent", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_dedent_removes_common_indentation_and_strips_by_default() -> None:
    """Common indentation and outer whitespace are removed."""

    ok, content, metadata = _run(text="\n        GPT-5.5\n          Claude Sonnet 4.6\n        Gemini 3.x\n")

    assert ok is True
    assert content == "GPT-5.5\n  Claude Sonnet 4.6\nGemini 3.x"
    assert metadata["strip"] is True
    assert metadata["chars"] == len(content)


def test_text_dedent_can_preserve_outer_whitespace() -> None:
    """strip=False retains blank edges after dedenting."""

    ok, content, metadata = _run(text="\n    Kimi K2\n", strip=False)

    assert ok is True
    assert content == "\nKimi K2\n"
    assert metadata["strip"] is False


def test_text_dedent_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies a boolean-like strip setting."""

    ok, content, metadata = _run(text="\n    one\n      two\n<<<TEXT_DEDENT>>>false")

    assert ok is True
    assert content == "\none\n  two\n"
    assert metadata["strip"] is False


def test_text_dedent_rejects_empty_oversized_and_invalid_strip() -> None:
    """Empty, oversized, and invalid strip inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_strip, content_strip, _m3 = _run(text="  value", strip="sometimes")
    ok_sentinel, content_sentinel, _m4 = _run(text="value<<<TEXT_DEDENT>>>false<<<TEXT_DEDENT>>>true")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_strip is False and "strip must be a boolean" in content_strip
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_text_dedent_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_dedent" in tools
    assert tools["text_dedent"].name == "text_dedent"
    SafetyPolicy().validate_tool("text_dedent")
    assert "text_dedent" in SafetyPolicy().allowed_tools
