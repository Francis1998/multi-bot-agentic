"""Tests for the bounded per-line title-casing tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_title_lines import TextTitleLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_title_lines tool."""

    result = TextTitleLinesTool().execute(ToolInvocation(tool_name="text_title_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_title_lines_titles_each_line_with_defaults() -> None:
    """Each line is independently title-cased with default options."""

    ok, content, metadata = _run(text="gpt-5.5 models\nclaude sonnet 4.6\r\ngemini 3.x")

    assert ok is True
    assert content == "Gpt-5.5 Models\nClaude Sonnet 4.6\r\nGemini 3.X"
    assert metadata["lines"] == 3
    assert metadata["titled_lines"] == 3
    assert metadata["skip_empty"] is True
    assert metadata["lowercase_first"] is False


def test_text_title_lines_preserves_empty_lines_and_line_endings() -> None:
    """Default skip_empty retains whitespace and all original ending styles."""

    ok, content, metadata = _run(text="GPT-5.5\r\n   \nKimi K2\r")

    assert ok is True
    assert content == "Gpt-5.5\r\n   \nKimi K2\r"
    assert metadata["skipped_empty_lines"] == 1
    assert metadata["skip_empty"] is True


def test_text_title_lines_supports_lowercase_first_and_empty_options() -> None:
    """Options can lowercase first and normalize whitespace-only line bodies."""

    ok, content, metadata = _run(
        text="GPT 5.5 MODELS\n   \nkimi k2",
        skip_empty=False,
        lowercase_first=True,
    )

    assert ok is True
    assert content == "Gpt 5.5 Models\n   \nKimi K2"
    assert metadata["titled_lines"] == 3
    assert metadata["skipped_empty_lines"] == 0
    assert metadata["lowercase_first"] is True


def test_text_title_lines_accepts_sentinel_options() -> None:
    """A directive payload can carry options after the sentinel."""

    ok, content, metadata = _run(text="claude SONNET 4.6\r\ngemini 3.x<<<TEXT_TITLE_LINES>>>true:true")

    assert ok is True
    assert content == "Claude Sonnet 4.6\r\nGemini 3.X"
    assert metadata["skip_empty"] is True
    assert metadata["lowercase_first"] is True


def test_text_title_lines_rejects_invalid_options_and_sentinel() -> None:
    """Booleans and sentinel syntax are strict."""

    invalid_arguments: list[dict[str, object]] = [
        {"skip_empty": "maybe"},
        {"lowercase_first": 1},
        {"skip_empty": 1},
    ]
    for arguments in invalid_arguments:
        ok, _content, _metadata = _run(text="value", **arguments)
        assert ok is False

    ok_suffix, content_suffix, _m1 = _run(text="value<<<TEXT_TITLE_LINES>>>true:false:extra")
    ok_duplicate, content_duplicate, _m2 = _run(text="value<<<TEXT_TITLE_LINES>>>true<<<TEXT_TITLE_LINES>>>true")
    assert ok_suffix is False and "sentinel suffix" in content_suffix
    assert ok_duplicate is False and "more than one" in content_duplicate


def test_text_title_lines_enforces_input_and_output_bounds() -> None:
    """Empty and oversized documents fail safely."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_input, content_input, metadata_input = _run(text="x" * 20_001)

    assert ok_empty is False and "empty" in content_empty
    assert ok_input is False and "max_chars" in content_input
    assert metadata_input["chars"] == 20_001


def test_text_title_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_title_lines" in tools
    assert tools["text_title_lines"].name == "text_title_lines"
    SafetyPolicy().validate_tool("text_title_lines")
    assert "text_title_lines" in SafetyPolicy().allowed_tools
