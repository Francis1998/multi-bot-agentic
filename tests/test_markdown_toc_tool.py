"""Tests for the Markdown TOC tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.markdown_toc import MarkdownTocTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the markdown_toc tool."""

    result = MarkdownTocTool().execute(ToolInvocation(tool_name="markdown_toc", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_markdown_toc_builds_nested_list() -> None:
    """ATX headings become a nested bullet TOC with slug anchors."""

    text = "# GPT-5.5\n\n## Claude Sonnet 4.6\n\n### Nested\n\n## Gemini 3.x\n"
    ok, content, metadata = _run(text=text)

    assert ok is True
    assert content == (
        "- [GPT-5.5](#gpt-55)\n"
        "  - [Claude Sonnet 4.6](#claude-sonnet-46)\n"
        "    - [Nested](#nested)\n"
        "  - [Gemini 3.x](#gemini-3x)\n"
    )
    assert metadata["headings"] == 4
    assert metadata["max_level"] == 3


def test_markdown_toc_respects_max_level_and_sentinel() -> None:
    """max_level filters deep headings; sentinel carries max_level."""

    text = "# A\n## B\n### C\n#### D\n"
    ok, content, metadata = _run(text=text, max_level=2)
    assert ok is True
    assert content == "- [A](#a)\n  - [B](#b)\n"
    assert metadata["headings"] == 2

    ok2, content2, metadata2 = _run(text=text + "<<<MARKDOWN_TOC>>>1")
    assert ok2 is True
    assert content2 == "- [A](#a)\n"
    assert metadata2["max_level"] == 1


def test_markdown_toc_rejects_invalid_and_bounds() -> None:
    """Empty, no headings, invalid max_level, oversized, duplicate sentinel fail."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_none, content_none, _m2 = _run(text="no headings here")
    ok_bad, content_bad, _m3 = _run(text="# A", max_level=0)
    ok_big, content_big, meta = _run(text="x" * 20_001)
    ok_dup, content_dup, _m4 = _run(text="# A<<<MARKDOWN_TOC>>>2<<<MARKDOWN_TOC>>>3")

    assert ok_empty is False and "empty" in content_empty
    assert ok_none is False and "no ATX headings" in content_none
    assert ok_bad is False and "max_level" in content_bad
    assert ok_big is False and "max_chars" in content_big and meta["chars"] == 20_001
    assert ok_dup is False and "more than one" in content_dup


def test_markdown_toc_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "markdown_toc" in tools
    assert tools["markdown_toc"].name == "markdown_toc"
    SafetyPolicy().validate_tool("markdown_toc")
    assert "markdown_toc" in SafetyPolicy().allowed_tools
