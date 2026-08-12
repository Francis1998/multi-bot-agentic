"""Tests for the hexadecimal encode tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.hex_encode import HexEncodeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the hex_encode tool."""

    result = HexEncodeTool().execute(ToolInvocation(tool_name="hex_encode", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_hex_encode_encodes_utf8_bytes_lowercase_by_default() -> None:
    """UTF-8 text becomes a lowercase hex string by default."""

    ok, content, metadata = _run(text="GPT-5.5")

    assert ok is True
    assert content == b"GPT-5.5".hex()
    assert metadata["uppercase"] is False
    assert metadata["input_chars"] == 7
    assert metadata["chars"] == len(content)


def test_hex_encode_can_emit_uppercase() -> None:
    """uppercase=true yields an uppercase hex digest."""

    ok, content, metadata = _run(text="Kimi K2", uppercase=True)

    assert ok is True
    assert content == b"Kimi K2".hex().upper()
    assert metadata["uppercase"] is True


def test_hex_encode_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies a boolean-like uppercase setting."""

    ok, content, metadata = _run(text="Claude Sonnet 4.6<<<HEX_ENCODE>>>true")

    assert ok is True
    assert content == b"Claude Sonnet 4.6".hex().upper()
    assert metadata["uppercase"] is True


def test_hex_encode_rejects_empty_oversized_and_invalid_uppercase() -> None:
    """Empty, oversized, and invalid uppercase inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_flag, content_flag, _m3 = _run(text="Gemini 3.x", uppercase="sometimes")
    ok_sentinel, content_sentinel, _m4 = _run(text="value<<<HEX_ENCODE>>>true<<<HEX_ENCODE>>>false")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_flag is False and "uppercase must be a boolean" in content_flag
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_hex_encode_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "hex_encode" in tools
    assert tools["hex_encode"].name == "hex_encode"
    SafetyPolicy().validate_tool("hex_encode")
    assert "hex_encode" in SafetyPolicy().allowed_tools
