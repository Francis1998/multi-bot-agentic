"""Tests for the whitespace squeeze tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_squeeze_ws import TextSqueezeWsTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_squeeze_ws tool."""

    result = TextSqueezeWsTool().execute(ToolInvocation(tool_name="text_squeeze_ws", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_squeeze_ws_collapses_all_whitespace_by_default() -> None:
    """Runs of spaces, tabs, and newlines collapse to a single space."""

    ok, content, metadata = _run(text="GPT-5.5\n\n  Claude\tSonnet  4.6")

    assert ok is True
    assert content == "GPT-5.5 Claude Sonnet 4.6"
    assert metadata["preserve_newlines"] is False
    assert metadata["input_chars"] == len("GPT-5.5\n\n  Claude\tSonnet  4.6")
    assert metadata["chars"] == len(content)


def test_text_squeeze_ws_can_preserve_newlines() -> None:
    """preserve_newlines=true only squeezes horizontal whitespace within lines."""

    ok, content, metadata = _run(
        text="Gemini  3.x\n\n  Kimi\tK2  ",
        preserve_newlines=True,
    )

    assert ok is True
    assert content == "Gemini 3.x\n\n Kimi K2 "
    assert metadata["preserve_newlines"] is True


def test_text_squeeze_ws_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies a boolean-like preserve_newlines setting."""

    ok, content, metadata = _run(text="a  b\nc  d<<<TEXT_SQUEEZE>>>true")

    assert ok is True
    assert content == "a b\nc d"
    assert metadata["preserve_newlines"] is True


def test_text_squeeze_ws_rejects_empty_oversized_and_invalid_bool() -> None:
    """Empty, oversized, and invalid preserve_newlines inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_flag, content_flag, _m3 = _run(text="value", preserve_newlines="sometimes")
    ok_sentinel, content_sentinel, _m4 = _run(text="value<<<TEXT_SQUEEZE>>>true<<<TEXT_SQUEEZE>>>false")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_flag is False and "preserve_newlines must be a boolean" in content_flag
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_text_squeeze_ws_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_squeeze_ws" in tools
    assert tools["text_squeeze_ws"].name == "text_squeeze_ws"
    SafetyPolicy().validate_tool("text_squeeze_ws")
    assert "text_squeeze_ws" in SafetyPolicy().allowed_tools
