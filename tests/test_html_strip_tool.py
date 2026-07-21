"""Tests for the deterministic HTML strip tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_strip import HtmlStripTool


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_strip tool for a document.

    Args:
        text: HTML document to strip.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = HtmlStripTool().execute(ToolInvocation(tool_name="html_strip", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_html_strip_removes_tags_and_keeps_text() -> None:
    """Tags are removed and character data is preserved as plain text."""

    ok, content, metadata = _run("<p>Hello <b>world</b></p>")

    assert ok is True
    assert content == "Hello world"
    assert metadata["chars"] == len(content)


def test_html_strip_unescapes_entities() -> None:
    """Named and numeric entities decode into their characters."""

    ok, content, _metadata = _run("<span>A&amp;B &#39;quote&#39;</span>")

    assert ok is True
    assert content == "A&B 'quote'"


def test_html_strip_rejects_script_content() -> None:
    """A document containing a script element is a structured failure.

    Leaking ``<script>`` bodies into plain text would let XSS payloads reach the
    durable event log. The tool must refuse the document rather than strip tags
    and return the script source.
    """

    ok, content, metadata = _run("<p>ok</p><script>alert(1)</script>")

    assert ok is False
    assert "script" in content
    assert metadata["rejected_tag"] == "script"


def test_html_strip_rejects_style_content() -> None:
    """A document containing a style element is a structured failure."""

    ok, content, metadata = _run("<style>body{display:none}</style><p>hi</p>")

    assert ok is False
    assert "style" in content
    assert metadata["rejected_tag"] == "style"


def test_html_strip_rejects_empty_document() -> None:
    """Whitespace-only input is a structured failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content


def test_html_strip_rejects_oversized_document() -> None:
    """A document above the char cap is a structured failure."""

    ok, content, metadata = _run("<p>" + ("x" * 20_000) + "</p>")

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_007


def test_html_strip_rejects_markup_only_document() -> None:
    """Tags with no visible text reduce to an empty-text failure."""

    ok, content, _metadata = _run("<div><br/></div>")

    assert ok is False
    assert "empty text" in content


def test_html_strip_is_registered_in_default_tools() -> None:
    """The html_strip tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "html_strip" in tools
    assert tools["html_strip"].name == "html_strip"
    assert "html_strip" in SafetyPolicy().allowed_tools
