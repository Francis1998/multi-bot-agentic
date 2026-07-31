"""Tests for the content-type sniffing tool."""

from __future__ import annotations

import base64
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.content_type_sniff import ContentTypeSniffTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the content_type_sniff tool with the given arguments."""

    result = ContentTypeSniffTool().execute(ToolInvocation(tool_name="content_type_sniff", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_content_type_sniff_detects_json() -> None:
    """Valid JSON objects are detected with high confidence."""

    ok, content, metadata = _run(text='{"model":"GPT-5.5","score":98}')

    assert ok is True
    assert content == "json"
    assert metadata["content_type"] == "json"
    assert metadata["confidence"] >= 0.95


def test_content_type_sniff_detects_xml() -> None:
    """XML declarations are detected as xml."""

    ok, content, metadata = _run(text='<?xml version="1.0"?><root><item>Gemini 3.x</item></root>')

    assert ok is True
    assert content == "xml"
    assert metadata["content_type"] == "xml"
    assert metadata["confidence"] >= 0.9


def test_content_type_sniff_detects_html() -> None:
    """HTML doctypes are detected as html."""

    ok, content, metadata = _run(text="<!DOCTYPE html><html><body><p>Claude Sonnet 4.6</p></body></html>")

    assert ok is True
    assert content == "html"
    assert metadata["content_type"] == "html"


def test_content_type_sniff_detects_tsv() -> None:
    """Tab-delimited tables are detected as tsv."""

    ok, content, metadata = _run(text="model\tscore\nKimi K2\t88\nGPT-5.5\t95\n")

    assert ok is True
    assert content == "tsv"
    assert metadata["content_type"] == "tsv"


def test_content_type_sniff_detects_markdown() -> None:
    """Markdown headings and lists are detected."""

    ok, content, metadata = _run(text="# Notes\n\n- item one\n- item two\n")

    assert ok is True
    assert content == "markdown"
    assert metadata["content_type"] == "markdown"


def test_content_type_sniff_accepts_base64_bytes_prefix() -> None:
    """A base64 byte prefix can be sniffed without a text argument."""

    payload = base64.b64encode(b'{"vendor":"Moonshot"}').decode("ascii")
    ok, content, metadata = _run(bytes_base64=payload)

    assert ok is True
    assert content == "json"
    assert metadata["content_type"] == "json"


def test_content_type_sniff_rejects_empty_document() -> None:
    """Whitespace-only input is a structured failure."""

    ok, content, _metadata = _run(text="   ")

    assert ok is False
    assert "empty" in content


def test_content_type_sniff_rejects_oversized_document() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_content_type_sniff_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "content_type_sniff" in tools
    assert tools["content_type_sniff"].name == "content_type_sniff"
    SafetyPolicy().validate_tool("content_type_sniff")
    assert "content_type_sniff" in SafetyPolicy().allowed_tools
