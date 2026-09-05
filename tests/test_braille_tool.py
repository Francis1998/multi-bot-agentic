"""Tests for the braille tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.braille import BrailleTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the braille tool."""

    result = BrailleTool().execute(ToolInvocation(tool_name="braille", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_braille_encode_hello() -> None:
    """encode mode maps ASCII into the U+2800 Braille block."""

    ok, content, metadata = _run(text="Hi", mode="encode")
    assert ok is True
    assert content == "\u2848\u2869"
    assert metadata["mode"] == "encode"
    assert metadata["out_chars"] == 2


def test_braille_decode_roundtrip() -> None:
    """decode mode reverses encode for ASCII text."""

    encoded = _run(text="ABC 123!", mode="encode")
    assert encoded[0] is True
    ok, content, metadata = _run(text=encoded[1], mode="decode")
    assert ok is True and content == "ABC 123!"
    assert metadata["mode"] == "decode"


def test_braille_default_mode_is_encode() -> None:
    """Omitting mode defaults to encode."""

    ok, content, metadata = _run(text="a")
    assert ok is True and content == "\u2861"
    assert metadata["mode"] == "encode"


def test_braille_rejects_non_ascii_and_non_braille() -> None:
    """Non-ASCII encode and non-Braille decode fail."""

    ok_enc, content_enc, _ = _run(text="café", mode="encode")
    assert ok_enc is False and "ASCII" in content_enc
    ok_dec, content_dec, _ = _run(text="plain", mode="decode")
    assert ok_dec is False and "Braille" in content_dec


def test_braille_rejects_empty_oversized_bad_mode_missing() -> None:
    """Structural failures for bad inputs and modes."""

    assert _run()[0] is False
    assert _run(text="")[0] is False
    ok_big, content_big, metadata_big = _run(text="A" * 2001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 2001
    ok_mode, content_mode, metadata_mode = _run(text="a", mode="hash")
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "hash"


def test_braille_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "braille" in tools
    assert tools["braille"].name == "braille"
    SafetyPolicy().validate_tool("braille")
    assert "braille" in SafetyPolicy().allowed_tools
