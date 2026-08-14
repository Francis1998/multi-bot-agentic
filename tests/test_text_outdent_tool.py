"""Tests for the bounded text outdent tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_outdent import TextOutdentTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_outdent tool."""

    result = TextOutdentTool().execute(ToolInvocation(tool_name="text_outdent", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_outdent_removes_up_to_two_spaces_by_default() -> None:
    """Varying indentation loses at most two spaces while blanks stay exact."""

    text = "    GPT-5.5\n \n Claude Sonnet 4.6\n\tGemini 3.x\n"
    ok, content, metadata = _run(text=text)

    assert ok is True
    assert content == "  GPT-5.5\n \nClaude Sonnet 4.6\n\tGemini 3.x\n"
    assert metadata["spaces"] == 2
    assert metadata["skip_first"] is False
    assert metadata["removed_spaces"] == 3
    assert metadata["input_chars"] == len(text)


def test_text_outdent_only_removes_ascii_spaces_and_preserves_endings() -> None:
    """Tabs are never removed and CRLF line endings are retained."""

    ok, content, metadata = _run(text="   Kimi K2\r\n  \r\n  \tvalue\r\n", spaces=3)

    assert ok is True
    assert content == "Kimi K2\r\n  \r\n\tvalue\r\n"
    assert metadata["removed_spaces"] == 5
    assert metadata["lines"] == 3


def test_text_outdent_supports_skip_first_and_zero_spaces() -> None:
    """skip_first protects line one and zero spaces is a no-op."""

    ok_skip, content_skip, metadata_skip = _run(
        text="    first\n    second\n",
        spaces=4,
        skip_first=True,
    )
    ok_zero, content_zero, metadata_zero = _run(text="  unchanged\n", spaces=0)

    assert ok_skip is True
    assert content_skip == "    first\nsecond\n"
    assert metadata_skip["skip_first"] is True
    assert metadata_skip["removed_spaces"] == 4
    assert ok_zero is True
    assert content_zero == "  unchanged\n"
    assert metadata_zero["removed_spaces"] == 0


def test_text_outdent_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies spaces and optional skip_first."""

    ok, content, metadata = _run(text="   a\n   b<<<TEXT_OUTDENT>>>3:true")

    assert ok is True
    assert content == "   a\nb"
    assert metadata["spaces"] == 3
    assert metadata["skip_first"] is True


def test_text_outdent_rejects_empty_oversized_and_invalid_options() -> None:
    """Empty, oversized, and invalid option inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_spaces, content_spaces, _m3 = _run(text="value", spaces=33)
    ok_flag, content_flag, _m4 = _run(text="value", skip_first="sometimes")
    ok_sentinel, content_sentinel, _m5 = _run(text="value<<<TEXT_OUTDENT>>>2<<<TEXT_OUTDENT>>>4")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_spaces is False and "spaces must be an integer" in content_spaces
    assert ok_flag is False and "skip_first must be a boolean" in content_flag
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_text_outdent_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_outdent" in tools
    assert tools["text_outdent"].name == "text_outdent"
    SafetyPolicy().validate_tool("text_outdent")
    assert "text_outdent" in SafetyPolicy().allowed_tools
