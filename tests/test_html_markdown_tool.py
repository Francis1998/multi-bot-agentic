"""Tests for the deterministic HTML-to-Markdown tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_markdown import HtmlMarkdownTool


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_markdown tool for a document.

    Args:
        text: HTML document to convert.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = HtmlMarkdownTool().execute(ToolInvocation(tool_name="html_markdown", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_html_markdown_converts_common_elements() -> None:
    """Headings, links, lists, emphasis, code, and paragraphs become Markdown."""

    html = (
        "<h1>Title</h1>"
        "<p>Hello <strong>world</strong> and <em>friends</em> with "
        '<a href="https://example.com">a link</a> and <code>x=1</code>.</p>'
        "<ul><li>one</li><li>two</li></ul>"
        "<ol><li>alpha</li><li>beta</li></ol>"
        "<pre>line1\nline2</pre>"
    )
    ok, content, metadata = _run(html)

    assert ok is True
    assert content.startswith("# Title")
    assert "**world**" in content
    assert "*friends*" in content
    assert "[a link](https://example.com)" in content
    assert "`x=1`" in content
    assert "- one" in content
    assert "- two" in content
    assert "1. alpha" in content
    assert "2. beta" in content
    assert "```\nline1\nline2\n```" in content
    assert metadata["chars"] == len(content)


def test_html_markdown_rejects_script_content() -> None:
    """A document containing a script element is a structured failure."""

    ok, content, metadata = _run("<p>ok</p><script>alert(1)</script>")

    assert ok is False
    assert "script" in content
    assert metadata["rejected_tag"] == "script"


def test_html_markdown_rejects_style_content() -> None:
    """A document containing a style element is a structured failure."""

    ok, content, metadata = _run("<style>body{display:none}</style><p>hi</p>")

    assert ok is False
    assert "style" in content
    assert metadata["rejected_tag"] == "style"


def test_html_markdown_rejects_empty_document() -> None:
    """Whitespace-only input is a structured failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content


def test_html_markdown_rejects_oversized_document() -> None:
    """A document above the char cap is a structured failure."""

    ok, content, metadata = _run("<p>" + ("x" * 20_000) + "</p>")

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_007


def test_html_markdown_is_registered_in_default_tools() -> None:
    """The html_markdown tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "html_markdown" in tools
    assert tools["html_markdown"].name == "html_markdown"
    assert "html_markdown" in SafetyPolicy().allowed_tools
