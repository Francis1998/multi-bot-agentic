"""Tests for the bounded text center lines tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_center_lines import TextCenterLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_center_lines tool."""

    result = TextCenterLinesTool().execute(ToolInvocation(tool_name="text_center_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_center_lines_centers_non_empty_lines() -> None:
    """Non-empty lines gain balanced ASCII spaces while blanks stay unchanged."""

    ok, content, metadata = _run(text="GPT-5.5\n\nKimi", width=12)

    assert ok is True
    assert content == "  GPT-5.5   \n\n    Kimi    "
    assert metadata["width"] == 12
    assert metadata["side"] == "both"
    assert metadata["skip_first"] is False
    assert metadata["centered_lines"] == 2


def test_text_center_lines_supports_skip_first_and_preserves_endings() -> None:
    """skip_first leaves line one untouched and original CRLF endings survive."""

    ok, content, metadata = _run(text="heading\r\nClaude\r\n", width=10, skip_first=True)

    assert ok is True
    assert content == "heading\r\n  Claude  \r\n"
    assert metadata["skip_first"] is True
    assert metadata["centered_lines"] == 1
    assert metadata["lines"] == 2


def test_text_center_lines_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies width and optional skip_first."""

    ok, content, metadata = _run(text="first\nGemini<<<TEXT_CENTER_LINES>>>10:true")

    assert ok is True
    assert content == "first\n  Gemini  "
    assert metadata["width"] == 10
    assert metadata["skip_first"] is True


def test_text_center_lines_rejects_empty_and_oversized_input() -> None:
    """Empty and oversized text fails structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001


def test_text_center_lines_rejects_width_outside_bounds() -> None:
    """Widths must be integers from 1 through 200."""

    for width in (0, 201, True, "wide"):
        ok, content, _metadata = _run(text="value", width=width)
        assert ok is False
        assert "width must be an integer" in content


def test_text_center_lines_rejects_invalid_skip_first() -> None:
    """skip_first accepts only boolean or recognized boolean text."""

    ok, content, _metadata = _run(text="value", skip_first="sometimes")

    assert ok is False
    assert "skip_first must be a boolean" in content


def test_text_center_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_center_lines" in tools
    assert tools["text_center_lines"].name == "text_center_lines"
    SafetyPolicy().validate_tool("text_center_lines")
    assert "text_center_lines" in SafetyPolicy().allowed_tools
