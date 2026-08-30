"""Tests for the crc32 tool."""

from __future__ import annotations

import zlib
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.crc32 import Crc32Tool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the crc32 tool."""

    result = Crc32Tool().execute(ToolInvocation(tool_name="crc32", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_crc32_known_utf8_digest() -> None:
    """CRC32 of a known string matches zlib."""

    text = "hello"
    expected = format(zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF, "x")
    ok, content, metadata = _run(text=text)

    assert ok is True
    assert content == expected
    assert metadata["crc32"] == expected
    assert metadata["chars"] == len(text)


def test_crc32_unicode_text() -> None:
    """UTF-8 text is hashed correctly."""

    text = "café"
    expected = format(zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF, "x")
    ok, content, _metadata = _run(text=text)

    assert ok is True
    assert content == expected


def test_crc32_rejects_missing_and_empty_text() -> None:
    """Missing or empty text fails structurally."""

    ok_missing, content_missing, _metadata = _run()
    ok_empty, content_empty, _metadata2 = _run(text="")

    assert ok_missing is False
    assert "missing required argument" in content_missing
    assert ok_empty is False
    assert "empty" in content_empty


def test_crc32_rejects_oversized_input() -> None:
    """Inputs over 100_000 chars fail."""

    ok, content, metadata = _run(text="x" * 100_001)
    assert ok is False
    assert "exceeds max" in content
    assert metadata["chars"] == 100_001


def test_crc32_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "crc32" in tools
    assert tools["crc32"].name == "crc32"
    SafetyPolicy().validate_tool("crc32")
    assert "crc32" in SafetyPolicy().allowed_tools
