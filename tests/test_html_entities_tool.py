"""Tests for the HTML entities encode/decode tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_entities import HtmlEntitiesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_entities tool with the given arguments."""

    result = HtmlEntitiesTool().execute(ToolInvocation(tool_name="html_entities", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_html_entities_encodes_ampersand_and_brackets() -> None:
    """Encode mode escapes &, <, and >."""

    ok, content, metadata = _run(text="A <B> & C", mode="encode")

    assert ok is True
    assert content == "A &lt;B&gt; &amp; C"
    assert metadata["mode"] == "encode"
    assert metadata["quote"] is True


def test_html_entities_encodes_quotes_when_enabled() -> None:
    """Encode with quote=True escapes double quotes."""

    ok, content, metadata = _run(text='say "hi"', mode="encode", quote=True)

    assert ok is True
    assert "&quot;" in content
    assert metadata["quote"] is True


def test_html_entities_skips_quotes_when_disabled() -> None:
    """Encode with quote=False leaves quotes intact."""

    ok, content, metadata = _run(text='say "hi"', mode="encode", quote=False)

    assert ok is True
    assert content == 'say "hi"'
    assert metadata["quote"] is False


def test_html_entities_decodes_named_and_numeric() -> None:
    """Decode mode unescapes named and numeric entities."""

    ok, content, metadata = _run(text="A &lt;B&gt; &#38; C", mode="decode")

    assert ok is True
    assert content == "A <B> & C"
    assert metadata["mode"] == "decode"
    assert cast(int, metadata["chars"]) == len(content)


def test_html_entities_defaults_to_encode() -> None:
    """Mode defaults to encode when omitted."""

    ok, content, metadata = _run(text="<x>")

    assert ok is True
    assert content == "&lt;x&gt;"
    assert metadata["mode"] == "encode"


def test_html_entities_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="")

    assert ok is False
    assert "empty" in content


def test_html_entities_rejects_oversized_text() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_html_entities_rejects_unsupported_mode() -> None:
    """Unknown modes are refused."""

    ok, content, metadata = _run(text="hi", mode="rot13")

    assert ok is False
    assert "unsupported mode" in content
    assert metadata["mode"] == "rot13"


def test_html_entities_rejects_invalid_quote() -> None:
    """Non-boolean quote values are refused."""

    ok, content, _metadata = _run(text="hi", quote="maybe")

    assert ok is False
    assert "quote" in content


def test_html_entities_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "html_entities" in tools
    assert tools["html_entities"].name == "html_entities"
    SafetyPolicy().validate_tool("html_entities")
    assert "html_entities" in SafetyPolicy().allowed_tools
