"""Tests for the caesar_cipher tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.caesar_cipher import CaesarCipherTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the caesar_cipher tool."""

    result = CaesarCipherTool().execute(ToolInvocation(tool_name="caesar_cipher", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_default_shift_13() -> None:
    """Default shift is ROT13-equivalent."""

    ok, content, metadata = _run(text="Hello")
    assert ok is True
    assert content == "Uryyb"
    assert isinstance(metadata["shift"], int)
    assert metadata["shift"] == 13


def test_shift_3_classic_caesar() -> None:
    """Classic Caesar shift of 3."""

    ok, content, _m = _run(text="ABC xyz", shift=3)
    assert ok is True
    assert content == "DEF abc"


def test_round_trip() -> None:
    """Encrypt then decrypt returns original."""

    ok1, encrypted, _m1 = _run(text="Secret!", shift=7)
    assert ok1 is True
    ok2, decrypted, _m2 = _run(text=encrypted, shift=26 - 7)
    assert ok2 is True
    assert decrypted == "Secret!"


def test_non_alpha_passthrough() -> None:
    """Non-alpha characters are preserved."""

    ok, content, _m = _run(text="1-2-3!", shift=5)
    assert ok is True
    assert content == "1-2-3!"


def test_rejects_empty_missing_oversized() -> None:
    """Structural failures."""

    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="A" * 20001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 20001


def test_invalid_shift_type() -> None:
    """Non-integer shift is rejected."""

    ok, content, _m = _run(text="hi", shift="abc")
    assert ok is False and "integer" in content


def test_caesar_cipher_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "caesar_cipher" in tools
    assert tools["caesar_cipher"].name == "caesar_cipher"
    SafetyPolicy().validate_tool("caesar_cipher")
    assert "caesar_cipher" in SafetyPolicy().allowed_tools
