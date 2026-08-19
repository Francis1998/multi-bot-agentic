"""Tests for the bounded text margin-lines tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_margin_lines import TextMarginLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_margin_lines tool."""

    result = TextMarginLinesTool().execute(ToolInvocation(tool_name="text_margin_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_margin_lines_adds_left_and_right_spaces() -> None:
    """Non-empty lines gain both margins while blank lines stay unchanged."""

    ok, content, metadata = _run(text="GPT-5.5\n\nKimi K2", left=2, right=3)

    assert ok is True
    assert content == "  GPT-5.5   \n\n  Kimi K2   "
    assert metadata["left"] == 2
    assert metadata["right"] == 3
    assert metadata["skip_first"] is False
    assert metadata["margined_lines"] == 2


def test_text_margin_lines_supports_skip_first_and_preserves_endings() -> None:
    """skip_first leaves line one untouched and CRLF endings survive."""

    ok, content, metadata = _run(
        text="heading\r\nClaude Sonnet 4.6\r\n",
        left=1,
        right=1,
        skip_first=True,
    )

    assert ok is True
    assert content == "heading\r\n Claude Sonnet 4.6 \r\n"
    assert metadata["skip_first"] is True
    assert metadata["lines"] == 2
    assert metadata["margined_lines"] == 1


def test_text_margin_lines_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies left, right, and skip_first."""

    ok, content, metadata = _run(text="first\nGemini 3.x<<<TEXT_MARGIN_LINES>>>2:1:true")

    assert ok is True
    assert content == "first\n  Gemini 3.x "
    assert metadata["left"] == 2
    assert metadata["right"] == 1
    assert metadata["skip_first"] is True


def test_text_margin_lines_defaults_to_zero_margins() -> None:
    """Omitted margins preserve the input and report no modified lines."""

    ok, content, metadata = _run(text="GPT-5.5\nKimi K2")

    assert ok is True
    assert content == "GPT-5.5\nKimi K2"
    assert metadata["left"] == 0
    assert metadata["right"] == 0
    assert metadata["margined_lines"] == 0


def test_text_margin_lines_rejects_empty_oversized_and_oversized_output() -> None:
    """Input and generated output enforce their character bounds."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_output, content_output, metadata_output = _run(text="x\n" * 100, left=200)

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    chars_big = metadata_big["chars"]
    assert isinstance(chars_big, int) and chars_big == 20_001
    assert ok_output is False and "output exceeds" in content_output
    chars_output = metadata_output["chars"]
    assert isinstance(chars_output, int) and chars_output > 20_000


def test_text_margin_lines_rejects_invalid_options_and_sentinel() -> None:
    """Margins and skip_first must stay within their strict option domains."""

    for name, value in (("left", -1), ("left", 201), ("right", True), ("right", "wide")):
        ok, content, _metadata = _run(text="value", **{name: value})
        assert ok is False
        assert f"{name} must be an integer" in content

    ok_skip, content_skip, _m1 = _run(text="value", skip_first="sometimes")
    ok_sentinel, content_sentinel, _m2 = _run(text="value<<<TEXT_MARGIN_LINES>>>2:true")
    ok_duplicate, content_duplicate, _m3 = _run(
        text="value<<<TEXT_MARGIN_LINES>>>1:1:false<<<TEXT_MARGIN_LINES>>>1:1:false"
    )

    assert ok_skip is False and "skip_first must be a boolean" in content_skip
    assert ok_sentinel is False and "left:right:skip_first" in content_sentinel
    assert ok_duplicate is False and "more than one" in content_duplicate


def test_text_margin_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_margin_lines" in tools
    assert tools["text_margin_lines"].name == "text_margin_lines"
    SafetyPolicy().validate_tool("text_margin_lines")
    assert "text_margin_lines" in SafetyPolicy().allowed_tools
