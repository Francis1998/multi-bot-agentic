"""Tests for the order-preserving unique-lines tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_unique_lines import TextUniqueLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_unique_lines tool."""

    result = TextUniqueLinesTool().execute(ToolInvocation(tool_name="text_unique_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_unique_lines_keeps_first_seen_order() -> None:
    """Duplicates drop; first occurrence order is preserved."""

    ok, content, metadata = _run(text="GPT-5.5\nClaude Sonnet 4.6\nGPT-5.5\nGemini 3.x\nClaude Sonnet 4.6")

    assert ok is True
    assert content == "GPT-5.5\nClaude Sonnet 4.6\nGemini 3.x\n"
    assert metadata["kept"] == 3
    assert metadata["dropped"] == 2
    assert metadata["strip"] is True


def test_text_unique_lines_strip_false_and_sentinel() -> None:
    """strip=false treats trailing spaces as distinct; sentinel works."""

    ok, content, metadata = _run(text="a \na\na ", strip=False)
    assert ok is True
    assert content == "a \na\n"
    assert metadata["kept"] == 2

    ok2, content2, metadata2 = _run(text="x\nx\ny<<<TEXT_UNIQUE_LINES>>>true")
    assert ok2 is True
    assert content2 == "x\ny"
    assert metadata2["strip"] is True


def test_text_unique_lines_preserves_crlf() -> None:
    """CRLF endings are preserved on kept lines."""

    ok, content, metadata = _run(text="Kimi K2\r\nKimi K2\r\nnext\r\n")
    assert ok is True
    assert content == "Kimi K2\r\nnext\r\n"
    assert metadata["dropped"] == 1


def test_text_unique_lines_rejects_invalid_and_bounds() -> None:
    """Empty, invalid strip, oversized, and duplicate sentinel fail."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_bad, content_bad, _m2 = _run(text="x", strip="nope")
    ok_big, content_big, meta = _run(text="x" * 20_001)
    ok_dup, content_dup, _m3 = _run(text="a<<<TEXT_UNIQUE_LINES>>>true<<<TEXT_UNIQUE_LINES>>>false")

    assert ok_empty is False and "empty" in content_empty
    assert ok_bad is False and "strip" in content_bad
    assert ok_big is False and "max_chars" in content_big and meta["chars"] == 20_001
    assert ok_dup is False and "more than one" in content_dup


def test_text_unique_lines_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_unique_lines" in tools
    assert tools["text_unique_lines"].name == "text_unique_lines"
    SafetyPolicy().validate_tool("text_unique_lines")
    assert "text_unique_lines" in SafetyPolicy().allowed_tools
