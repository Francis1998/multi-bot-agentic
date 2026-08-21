"""Tests for the bounded per-line slugification tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_slug_lines import TextSlugLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_slug_lines tool."""

    result = TextSlugLinesTool().execute(ToolInvocation(tool_name="text_slug_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_slug_lines_slugifies_each_line_with_defaults() -> None:
    """Each line is independently normalized with the default separator."""

    ok, content, metadata = _run(text="Café Models!\nClaude Sonnet 4.6\r\nGemini 3.x")

    assert ok is True
    assert content == "cafe-models\nclaude-sonnet-4-6\r\ngemini-3-x"
    assert metadata["lines"] == 3
    assert metadata["slugged_lines"] == 3
    assert metadata["separator"] == "-"
    assert metadata["lowercase"] is True


def test_text_slug_lines_preserves_empty_lines_and_line_endings() -> None:
    """Default skip_empty retains whitespace and all original ending styles."""

    ok, content, metadata = _run(text="GPT-5.5\r\n   \nKimi K2\r")

    assert ok is True
    assert content == "gpt-5-5\r\n   \nkimi-k2\r"
    assert metadata["skipped_empty_lines"] == 1
    assert metadata["skip_empty"] is True


def test_text_slug_lines_supports_separator_case_and_empty_options() -> None:
    """Options can retain case and normalize whitespace-only line bodies."""

    ok, content, metadata = _run(
        text="GPT 5.5\n   \nKimi K2",
        separator="_",
        lowercase=False,
        skip_empty=False,
    )

    assert ok is True
    assert content == "GPT_5_5\n\nKimi_K2"
    assert metadata["slugged_lines"] == 3
    assert metadata["skipped_empty_lines"] == 0


def test_text_slug_lines_accepts_sentinel_options() -> None:
    """A directive payload can carry all options after the sentinel."""

    ok, content, metadata = _run(text="Claude Sonnet 4.6\r\nGemini 3.x<<<TEXT_SLUG_LINES>>>_:false:true")

    assert ok is True
    assert content == "Claude_Sonnet_4_6\r\nGemini_3_x"
    assert metadata["separator"] == "_"
    assert metadata["lowercase"] is False
    assert metadata["skip_empty"] is True


def test_text_slug_lines_handles_lines_that_reduce_to_empty() -> None:
    """Punctuation-only lines become empty without failing the document."""

    ok, content, metadata = _run(text="GPT-5.5\n!!!\nKimi K2")

    assert ok is True
    assert content == "gpt-5-5\n\nkimi-k2"
    assert metadata["slugged_lines"] == 3


def test_text_slug_lines_rejects_invalid_options_and_sentinel() -> None:
    """Separators, booleans, and sentinel syntax are strict."""

    invalid_arguments: list[dict[str, object]] = [
        {"separator": ""},
        {"separator": "/"},
        {"separator": "x" * 9},
        {"lowercase": "maybe"},
        {"skip_empty": 1},
    ]
    for arguments in invalid_arguments:
        ok, _content, _metadata = _run(text="value", **arguments)
        assert ok is False

    ok_suffix, content_suffix, _m1 = _run(text="value<<<TEXT_SLUG_LINES>>>_:true:false:extra")
    ok_duplicate, content_duplicate, _m2 = _run(text="value<<<TEXT_SLUG_LINES>>>_:true<<<TEXT_SLUG_LINES>>>_:true")
    assert ok_suffix is False and "sentinel suffix" in content_suffix
    assert ok_duplicate is False and "more than one" in content_duplicate


def test_text_slug_lines_enforces_input_and_output_bounds() -> None:
    """Empty, oversized, and over-expanded documents fail safely."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_input, content_input, metadata_input = _run(text="x" * 20_001)
    ok_output, content_output, metadata_output = _run(
        text=("a b c d e f g h i j\n" * 952).rstrip("\n"),
        separator="abcdefgh",
    )

    assert ok_empty is False and "empty" in content_empty
    assert ok_input is False and "max_chars" in content_input
    assert metadata_input["chars"] == 20_001
    assert ok_output is False and "output exceeds" in content_output
    chars = metadata_output["chars"]
    assert isinstance(chars, int) and chars > 20_000


def test_text_slug_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_slug_lines" in tools
    assert tools["text_slug_lines"].name == "text_slug_lines"
    SafetyPolicy().validate_tool("text_slug_lines")
    assert "text_slug_lines" in SafetyPolicy().allowed_tools
