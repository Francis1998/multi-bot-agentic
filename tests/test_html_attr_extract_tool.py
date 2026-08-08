"""Tests for the HTML attribute extraction tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_attr_extract import HtmlAttrExtractTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_attr_extract tool with the given arguments."""

    result = HtmlAttrExtractTool().execute(ToolInvocation(tool_name="html_attr_extract", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


_HTML = '<html><body><a href="/a">A</a><img src="/i.png" alt="x"/><a href="/b">B</a></body></html>'


def test_html_attr_extract_all_hrefs() -> None:
    """Extracts every href when no tag filter is set."""

    ok, content, metadata = _run(text=_HTML, attr="href")

    assert ok is True
    assert content.splitlines() == ["/a", "/b"]
    assert cast(int, metadata["count"]) == 2
    assert metadata["attr"] == "href"


def test_html_attr_extract_filters_by_tag() -> None:
    """Optional tag filter limits which elements are scanned."""

    ok, content, metadata = _run(text=_HTML, attr="src", tag="img")

    assert ok is True
    assert content == "/i.png"
    assert cast(int, metadata["count"]) == 1
    assert metadata["tag"] == "img"


def test_html_attr_extract_respects_max_results() -> None:
    """max_results caps the number of returned values."""

    ok, content, metadata = _run(text=_HTML, attr="href", max_results=1)

    assert ok is True
    assert content == "/a"
    assert cast(int, metadata["count"]) == 1
    assert metadata["truncated"] is True


def test_html_attr_extract_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="", attr="href")

    assert ok is False
    assert "empty" in content


def test_html_attr_extract_rejects_missing_attr() -> None:
    """Missing attr name is refused."""

    ok, content, _metadata = _run(text=_HTML, attr="")

    assert ok is False
    assert "attr is required" in content


def test_html_attr_extract_rejects_oversized() -> None:
    """Documents over the char bound are refused."""

    ok, content, metadata = _run(text="<a href='x'></a>" + ("x" * 20_000), attr="href")

    assert ok is False
    assert "max_chars" in content
    assert cast(int, metadata["chars"]) > 20_000


def test_html_attr_extract_is_registered_in_default_tools(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "html_attr_extract" in tools
    assert tools["html_attr_extract"].name == "html_attr_extract"
    SafetyPolicy().validate_tool("html_attr_extract")
    assert "html_attr_extract" in SafetyPolicy().allowed_tools
