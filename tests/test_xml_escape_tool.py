"""Tests for the xml_escape tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.xml_escape import XmlEscapeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the xml_escape tool."""

    result = XmlEscapeTool().execute(ToolInvocation(tool_name="xml_escape", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_xml_escape_escapes_ampersand_and_brackets_by_default() -> None:
    """Default mode escapes &, <, and >."""

    ok, content, metadata = _run(text="A <B> & C")

    assert ok is True
    assert content == "A &lt;B&gt; &amp; C"
    assert metadata["mode"] == "escape"
    assert metadata["chars"] == len(content)


def test_xml_escape_unescapes_entities() -> None:
    """Unescape mode restores special characters."""

    ok, content, metadata = _run(text="A &lt;B&gt; &amp; C", mode="unescape")

    assert ok is True
    assert content == "A <B> & C"
    assert metadata["mode"] == "unescape"


def test_xml_escape_rejects_empty_oversized_and_unsupported_mode() -> None:
    """Empty, oversized, and unknown modes fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_mode, content_mode, metadata_mode = _run(text="hi", mode="encode")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "encode"


def test_xml_escape_mentions_model_versions_as_examples() -> None:
    """Escaping stays deterministic for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."""

    ok, content, metadata = _run(text="GPT-5.5 < Claude Sonnet 4.6 & Gemini 3.x / Kimi K2")

    assert ok is True
    assert "&lt;" in content and "&amp;" in content
    assert "Kimi K2" in content
    assert metadata["mode"] == "escape"


def test_xml_escape_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "xml_escape" in tools
    assert tools["xml_escape"].name == "xml_escape"
    SafetyPolicy().validate_tool("xml_escape")
    assert "xml_escape" in SafetyPolicy().allowed_tools
