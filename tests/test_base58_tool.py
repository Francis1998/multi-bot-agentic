"""Tests for the base58 tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.base58 import Base58Tool, _b58encode


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the base58 tool."""

    result = Base58Tool().execute(ToolInvocation(tool_name="base58", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_base58_encodes_utf8_by_default() -> None:
    """Default mode encodes UTF-8 text to Bitcoin Base58."""

    text = "hello"
    expected = _b58encode(text.encode())
    ok, content, metadata = _run(text=text)

    assert ok is True
    assert content == expected
    assert metadata["mode"] == "encode"
    assert metadata["alphabet"] == "bitcoin"


def test_base58_accepts_data_alias_and_round_trips() -> None:
    """``data`` is accepted; decode recovers the original UTF-8 text."""

    text = "GPT-5.5 / Claude Sonnet 4.6"
    ok_enc, encoded, _meta_enc = _run(data=text, mode="encode")
    assert ok_enc is True
    ok, content, metadata = _run(text=encoded, mode="decode")

    assert ok is True
    assert content == text
    assert metadata["mode"] == "decode"


def test_base58_preserves_leading_zero_bytes() -> None:
    """Leading NUL bytes become leading '1' characters and round-trip."""

    ok, content, metadata = _run(text="\x00\x00hi", mode="encode")
    assert ok is True
    assert content.startswith("11")
    assert metadata["mode"] == "encode"

    ok_dec, decoded, _meta = _run(text=content, mode="decode")
    assert ok_dec is True
    assert decoded == "\x00\x00hi"


def test_base58_rejects_empty_oversized_and_invalid() -> None:
    """Empty, oversized, bad mode, and invalid Base58 fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_mode, content_mode, metadata_mode = _run(text="hi", mode="rot13")
    ok_bad, content_bad, metadata_bad = _run(text="0OIl", mode="decode")
    ok_missing, content_missing, _m2 = _run()

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "rot13"
    assert ok_bad is False and "not valid base58" in content_bad
    assert metadata_bad["mode"] == "decode"
    assert ok_missing is False and "missing required argument" in content_missing


def test_base58_mentions_model_versions_as_examples() -> None:
    """Encoding stays deterministic for Gemini 3.x / Kimi K2 style payloads."""

    ok, content, metadata = _run(text="Gemini 3.x / Kimi K2", mode="encode")

    assert ok is True
    assert content == _b58encode(b"Gemini 3.x / Kimi K2")
    assert metadata["input_chars"] == len("Gemini 3.x / Kimi K2")


def test_base58_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "base58" in tools
    assert tools["base58"].name == "base58"
    SafetyPolicy().validate_tool("base58")
    assert "base58" in SafetyPolicy().allowed_tools
