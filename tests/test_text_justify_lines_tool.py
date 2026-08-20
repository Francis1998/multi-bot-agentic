"""Tests for the bounded text line-justification tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_justify_lines import TextJustifyLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_justify_lines tool."""

    result = TextJustifyLinesTool().execute(ToolInvocation(tool_name="text_justify_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_justify_lines_supports_left_right_and_center_alignment() -> None:
    """The three padding alignments reach the requested width."""

    ok_left, left, metadata_left = _run(text="Kimi K2", width=10, alignment="left")
    ok_right, right, metadata_right = _run(text="Kimi K2", width=10, align="right")
    ok_center, center, metadata_center = _run(text="Kimi K2", width=11, mode="center")

    assert ok_left is True and left == "Kimi K2   "
    assert ok_right is True and right == "   Kimi K2"
    assert ok_center is True and center == "  Kimi K2  "
    assert metadata_left["alignment"] == "left"
    assert metadata_right["alignment"] == "right"
    assert metadata_center["alignment"] == "center"


def test_text_justify_lines_distributes_spaces_for_full_justification() -> None:
    """Full justification spreads extra spaces across gaps from the left."""

    ok, content, metadata = _run(
        text="GPT-5.5 Claude Sonnet Kimi\nGemini",
        width=30,
        alignment="justify",
    )

    assert ok is True
    assert content == "GPT-5.5   Claude  Sonnet  Kimi\nGemini                        "
    assert metadata["formatted_lines"] == 2
    assert all(len(line) == 30 for line in content.splitlines())


def test_text_justify_lines_preserves_blank_lines_and_long_content() -> None:
    """Blank lines and content that cannot fit are not truncated."""

    ok, content, metadata = _run(
        text="GPT-5.5\n\nClaude Sonnet 4.6",
        width=10,
        alignment="right",
    )

    assert ok is True
    assert content == "   GPT-5.5\n\nClaude Sonnet 4.6"
    assert metadata["lines"] == 3
    assert metadata["formatted_lines"] == 1


def test_text_justify_lines_accepts_sentinel_and_preserves_endings() -> None:
    """Sentinel options support skip_first while retaining CRLF endings."""

    ok, content, metadata = _run(text="heading\r\nGemini 3.x\r\n<<<TEXT_JUSTIFY_LINES>>>14:right:true")

    assert ok is True
    assert content == "heading\r\n    Gemini 3.x\r\n"
    assert metadata["width"] == 14
    assert metadata["skip_first"] is True


def test_text_justify_lines_defaults_to_width_80_and_left_alignment() -> None:
    """Omitted options use the documented formatting defaults."""

    ok, content, metadata = _run(text="GPT-5.5")

    assert ok is True
    assert len(content) == 80
    assert content.startswith("GPT-5.5")
    assert metadata["width"] == 80
    assert metadata["alignment"] == "left"


def test_text_justify_lines_rejects_invalid_options_and_sentinel() -> None:
    """Widths, alignments, booleans, and sentinel syntax are strict."""

    invalid_arguments: list[dict[str, object]] = [
        {"width": 0},
        {"width": 501},
        {"width": True},
        {"alignment": "diagonal"},
        {"skip_first": "sometimes"},
        {"alignment": "left", "mode": "right"},
    ]
    for arguments in invalid_arguments:
        ok, _content, _metadata = _run(text="value", **arguments)
        assert ok is False

    ok_suffix, content_suffix, _m1 = _run(text="value<<<TEXT_JUSTIFY_LINES>>>20:left:false:extra")
    ok_duplicate, content_duplicate, _m2 = _run(
        text="value<<<TEXT_JUSTIFY_LINES>>>20:left:false<<<TEXT_JUSTIFY_LINES>>>20:left:false"
    )
    assert ok_suffix is False and "sentinel suffix" in content_suffix
    assert ok_duplicate is False and "more than one" in content_duplicate


def test_text_justify_lines_enforces_input_and_output_bounds() -> None:
    """Input and generated output cannot exceed 20,000 characters."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_input, content_input, metadata_input = _run(text="x" * 20_001)
    ok_output, content_output, metadata_output = _run(text="x\n" * 100, width=500)

    assert ok_empty is False and "empty" in content_empty
    assert ok_input is False and "max_chars" in content_input
    assert metadata_input["chars"] == 20_001
    assert ok_output is False and "output exceeds" in content_output
    chars = metadata_output["chars"]
    assert isinstance(chars, int) and chars > 20_000


def test_text_justify_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_justify_lines" in tools
    assert tools["text_justify_lines"].name == "text_justify_lines"
    SafetyPolicy().validate_tool("text_justify_lines")
    assert "text_justify_lines" in SafetyPolicy().allowed_tools
