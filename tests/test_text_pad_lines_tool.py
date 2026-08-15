"""Tests for the bounded text pad lines tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_pad_lines import TextPadLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_pad_lines tool."""

    result = TextPadLinesTool().execute(ToolInvocation(tool_name="text_pad_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_pad_lines_pads_to_width_on_the_right_by_default() -> None:
    """Non-empty lines gain trailing spaces to reach the default width."""

    text = "GPT-5.5\n\nClaude"
    ok, content, metadata = _run(text=text, width=12)

    assert ok is True
    assert content == "GPT-5.5     \n\nClaude      "
    assert metadata["width"] == 12
    assert metadata["side"] == "right"
    assert metadata["skip_first"] is False
    assert metadata["padded_lines"] == 2


def test_text_pad_lines_supports_left_both_and_skip_first() -> None:
    """side and skip_first control padding placement and first-line behavior."""

    ok_left, content_left, metadata_left = _run(text="Kimi", width=6, side="left")
    ok_both, content_both, metadata_both = _run(text="Gemini", width=8, side="both")
    ok_skip, content_skip, metadata_skip = _run(
        text="first\nsecond\n",
        width=8,
        side="right",
        skip_first=True,
    )

    assert ok_left is True
    assert content_left == "  Kimi"
    assert metadata_left["side"] == "left"
    assert ok_both is True
    assert content_both == " Gemini "
    assert metadata_both["side"] == "both"
    assert ok_skip is True
    assert content_skip == "first\nsecond  \n"
    assert metadata_skip["skip_first"] is True
    assert metadata_skip["padded_lines"] == 1


def test_text_pad_lines_preserves_blank_lines_and_line_endings() -> None:
    """Blank lines and CRLF endings remain unchanged."""

    ok, content, metadata = _run(text="a\r\n  \r\nb\r\n", width=4, side="right")

    assert ok is True
    assert content == "a   \r\n  \r\nb   \r\n"
    assert metadata["lines"] == 3


def test_text_pad_lines_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies width, side, and optional skip_first."""

    ok, content, metadata = _run(text="a\nb<<<TEXT_PAD_LINES>>>6:both:true")

    assert ok is True
    assert content == "a\n  b   "
    assert metadata["width"] == 6
    assert metadata["side"] == "both"
    assert metadata["skip_first"] is True


def test_text_pad_lines_rejects_empty_oversized_and_invalid_options() -> None:
    """Empty, oversized, and invalid option inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_width, content_width, _m3 = _run(text="value", width=201)
    ok_side, content_side, _m4 = _run(text="value", side="center")
    ok_flag, content_flag, _m5 = _run(text="value", skip_first="sometimes")
    ok_sentinel, content_sentinel, _m6 = _run(text="value<<<TEXT_PAD_LINES>>>8<<<TEXT_PAD_LINES>>>10")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_width is False and "width must be an integer" in content_width
    assert ok_side is False and "side must be left" in content_side
    assert ok_flag is False and "skip_first must be a boolean" in content_flag
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_text_pad_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_pad_lines" in tools
    assert tools["text_pad_lines"].name == "text_pad_lines"
    SafetyPolicy().validate_tool("text_pad_lines")
    assert "text_pad_lines" in SafetyPolicy().allowed_tools
