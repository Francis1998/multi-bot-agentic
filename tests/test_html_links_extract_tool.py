"""Tests for the HTML links extract tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_links_extract import HtmlLinksExtractTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_links_extract tool."""

    result = HtmlLinksExtractTool().execute(ToolInvocation(tool_name="html_links_extract", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_html_links_extract_collects_href_and_text() -> None:
    """Anchors become JSON href/text pairs."""

    html = '<p><a href="https://openai.com">GPT-5.5</a> and <a href="/claude">Claude Sonnet 4.6</a></p>'
    ok, content, metadata = _run(html=html)

    assert ok is True
    assert json.loads(content) == [
        {"href": "https://openai.com", "text": "GPT-5.5"},
        {"href": "/claude", "text": "Claude Sonnet 4.6"},
    ]
    assert metadata["links"] == 2


def test_html_links_extract_respects_max_links_and_text_alias() -> None:
    """max_links bounds output; text alias works."""

    html = '<a href="/a">A</a><a href="/b">B</a><a href="/c">C</a>'
    ok, content, metadata = _run(text=html, max_links=2)
    assert ok is True
    assert len(json.loads(content)) == 2
    assert metadata["max_links"] == 2


def test_html_links_extract_rejects_script_style_and_bounds() -> None:
    """script/style, empty, no links, invalid max_links, oversized fail."""

    ok_script, content_script, _m1 = _run(html='<script>x</script><a href="/a">A</a>')
    ok_empty, content_empty, _m2 = _run(html="   ")
    ok_none, content_none, _m3 = _run(html="<p>no links</p>")
    ok_bad, content_bad, _m4 = _run(html='<a href="/a">A</a>', max_links=0)
    ok_big, content_big, meta = _run(html="x" * 20_001)

    assert ok_script is False and "script or style" in content_script
    assert ok_empty is False and "empty" in content_empty
    assert ok_none is False and "no links" in content_none
    assert ok_bad is False and "max_links" in content_bad
    assert ok_big is False and "max_chars" in content_big and meta["chars"] == 20_001


def test_html_links_extract_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "html_links_extract" in tools
    assert tools["html_links_extract"].name == "html_links_extract"
    SafetyPolicy().validate_tool("html_links_extract")
    assert "html_links_extract" in SafetyPolicy().allowed_tools
