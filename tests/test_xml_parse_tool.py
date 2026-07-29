"""Tests for the XML parsing tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.xml_parse import XmlParseTool


def _run(document: str) -> tuple[bool, str]:
    """Execute the xml_parse tool for a document.

    Args:
        document: XML document text to parse.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = XmlParseTool().execute(ToolInvocation(tool_name="xml_parse", arguments={"text": document}))
    return result.ok, result.content


def test_xml_parse_renders_tree_with_attributes_and_text() -> None:
    """A valid document is summarized with tags, attributes, and text nodes."""

    ok, content = _run(
        """<models>
  <model vendor="OpenAI">GPT-5.5</model>
  <model vendor="Anthropic">Claude Sonnet 4.6</model>
</models>"""
    )

    assert ok is True
    assert "models" in content
    assert "model @vendor=OpenAI" in content
    assert "GPT-5.5" in content
    assert "Claude Sonnet 4.6" in content


def test_xml_parse_rejects_doctype() -> None:
    """Documents containing a DOCTYPE declaration are rejected before parse."""

    ok, content = _run("<!DOCTYPE foo><root/>")

    assert ok is False
    assert "DOCTYPE" in content or "disallowed" in content


def test_xml_parse_rejects_entity() -> None:
    """Documents containing an ENTITY declaration are rejected before parse."""

    ok, content = _run("<!ENTITY xxe SYSTEM 'file:///etc/passwd'><root/>")

    assert ok is False
    assert "ENTITY" in content or "disallowed" in content


def test_xml_parse_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_xml_parse_rejects_oversized_document() -> None:
    """Documents above the fixed character cap are refused before parsing."""

    ok, content = _run("<root>" + ("x" * 20_001) + "</root>")

    assert ok is False
    assert "max_chars=20000" in content


def test_xml_parse_rejects_malformed_document() -> None:
    """Malformed XML returns a structured parse failure."""

    ok, content = _run("<root><unclosed>")

    assert ok is False
    assert "invalid XML" in content


def test_xml_parse_truncates_deep_trees() -> None:
    """Trees deeper than the render cap include a depth-limit marker."""

    document = "<root>" + "<child>" * 20 + "leaf" + "</child>" * 20 + "</root>"
    result = XmlParseTool().execute(ToolInvocation(tool_name="xml_parse", arguments={"text": document}))

    assert result.ok is True
    assert "[depth limit]" in result.content
    assert result.metadata["truncated_depth"] is True


def test_xml_parse_truncates_large_element_counts() -> None:
    """Trees with more than the element cap include an element-limit marker."""

    items = "".join(f"<item id='{index}'/>" for index in range(600))
    result = XmlParseTool().execute(ToolInvocation(tool_name="xml_parse", arguments={"text": f"<root>{items}</root>"}))

    assert result.ok is True
    assert "[element limit]" in result.content
    assert result.metadata["truncated_elements"] is True


def test_xml_parse_reports_metadata() -> None:
    """Successful results include element and path metadata."""

    result = XmlParseTool().execute(
        ToolInvocation(
            tool_name="xml_parse",
            arguments={
                "text": "<suite><model>Gemini 3.x</model><model>Kimi K2</model></suite>",
            },
        )
    )

    assert result.ok is True
    assert "Gemini 3.x" in result.content
    assert "Kimi K2" in result.content
    assert result.metadata["element_count"] == 3
    assert result.metadata["path_count"] >= 2


def test_xml_parse_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is available through the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "xml_parse" in tools
    assert tools["xml_parse"].name == "xml_parse"
    SafetyPolicy().validate_tool("xml_parse")
    assert "xml_parse" in SafetyPolicy().allowed_tools
