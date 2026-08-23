"""Tests for the blank-line collapsing tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_collapse_blank import TextCollapseBlankTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_collapse_blank tool."""

    result = TextCollapseBlankTool().execute(ToolInvocation(tool_name="text_collapse_blank", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_collapse_blank_collapses_runs_to_default() -> None:
    """Default max_blank=1 collapses longer blank runs."""

    ok, content, metadata = _run(text="GPT-5.5\n\n\n\nClaude Sonnet 4.6\n\n\nGemini 3.x")

    assert ok is True
    assert content == "GPT-5.5\n\nClaude Sonnet 4.6\n\nGemini 3.x"
    assert metadata["max_blank"] == 1
    assert metadata["collapsed_runs"] == 3
    assert metadata["non_blank_lines"] == 3


def test_text_collapse_blank_supports_max_blank_zero_and_sentinel() -> None:
    """max_blank=0 removes blanks; sentinel carries max_blank."""

    ok, content, metadata = _run(text="a\n\n\nb", max_blank=0)
    assert ok is True
    assert content == "a\nb"
    assert metadata["kept_blank_lines"] == 0

    ok2, content2, metadata2 = _run(text="a\n\n\n\nb<<<TEXT_COLLAPSE_BLANK>>>2")
    assert ok2 is True
    assert content2 == "a\n\n\nb"
    assert metadata2["max_blank"] == 2


def test_text_collapse_blank_preserves_crlf_and_whitespace_only_as_blank() -> None:
    """CRLF endings and whitespace-only lines count as blank."""

    ok, content, metadata = _run(text="Kimi K2\r\n   \r\n\r\nnext")

    assert ok is True
    assert content == "Kimi K2\r\n   \r\nnext"
    assert metadata["kept_blank_lines"] == 1


def test_text_collapse_blank_rejects_invalid_and_bounds() -> None:
    """Empty, invalid max_blank, oversized, and duplicate sentinel fail."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_bad, content_bad, _m2 = _run(text="x", max_blank="nope")
    ok_big, content_big, meta = _run(text="x" * 20_001)
    ok_dup, content_dup, _m3 = _run(text="a<<<TEXT_COLLAPSE_BLANK>>>1<<<TEXT_COLLAPSE_BLANK>>>1")

    assert ok_empty is False and "empty" in content_empty
    assert ok_bad is False and "max_blank" in content_bad
    assert ok_big is False and "max_chars" in content_big and meta["chars"] == 20_001
    assert ok_dup is False and "more than one" in content_dup


def test_text_collapse_blank_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_collapse_blank" in tools
    assert tools["text_collapse_blank"].name == "text_collapse_blank"
    SafetyPolicy().validate_tool("text_collapse_blank")
    assert "text_collapse_blank" in SafetyPolicy().allowed_tools
