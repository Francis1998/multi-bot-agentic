"""Tests for the text wrapping tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_wrap import TextWrapTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_wrap tool with the given arguments."""

    result = TextWrapTool().execute(ToolInvocation(tool_name="text_wrap", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_wrap_wraps_lines() -> None:
    """Wrap mode joins wrapped segments with newlines."""

    ok, content, metadata = _run(text="GPT-5.5 Claude Sonnet 4.6 Gemini 3.x Kimi K2", width=12, mode="wrap")

    assert ok is True
    assert "\n" in content
    assert metadata["mode"] == "wrap"
    assert cast(int, metadata["width"]) == 12
    assert cast(int, metadata["lines"]) >= 2


def test_text_wrap_fills_paragraph() -> None:
    """Fill mode returns reflowed text via textwrap.fill."""

    ok, content, metadata = _run(
        text="one two three four five six seven eight nine ten",
        width=20,
        mode="fill",
    )

    assert ok is True
    assert metadata["mode"] == "fill"
    assert content
    assert cast(int, metadata["lines"]) >= 1


def test_text_wrap_defaults_to_width_80() -> None:
    """Width defaults to 80 when omitted."""

    ok, _content, metadata = _run(text="short line")

    assert ok is True
    assert metadata["width"] == 80
    assert metadata["mode"] == "wrap"


def test_text_wrap_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="")

    assert ok is False
    assert "empty" in content


def test_text_wrap_rejects_oversized_text() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_text_wrap_rejects_invalid_width() -> None:
    """Out-of-range widths are refused."""

    ok, content, _metadata = _run(text="hello", width=0)

    assert ok is False
    assert "width" in content


def test_text_wrap_rejects_unsupported_mode() -> None:
    """Unknown modes are refused."""

    ok, content, metadata = _run(text="hello", mode="justify")

    assert ok is False
    assert "unsupported mode" in content
    assert metadata["mode"] == "justify"


def test_text_wrap_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_wrap" in tools
    assert tools["text_wrap"].name == "text_wrap"
    SafetyPolicy().validate_tool("text_wrap")
    assert "text_wrap" in SafetyPolicy().allowed_tools
