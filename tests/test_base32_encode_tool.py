"""Tests for the base32_encode tool."""

from __future__ import annotations

import base64
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.base32_encode import Base32EncodeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the base32_encode tool."""

    result = Base32EncodeTool().execute(ToolInvocation(tool_name="base32_encode", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_base32_encode_encodes_utf8_by_default() -> None:
    """Default mode encodes UTF-8 text to standard Base32."""

    text = "hello"
    expected = base64.b32encode(text.encode()).decode("ascii")
    ok, content, metadata = _run(text=text)

    assert ok is True
    assert content == expected
    assert metadata["mode"] == "encode"
    assert metadata["alphabet"] == "standard"


def test_base32_encode_round_trips_decode() -> None:
    """Decode mode recovers the original UTF-8 text."""

    text = "GPT-5.5 / Claude Sonnet 4.6"
    encoded = base64.b32encode(text.encode()).decode("ascii")
    ok, content, metadata = _run(text=encoded, mode="decode")

    assert ok is True
    assert content == text
    assert metadata["mode"] == "decode"


def test_base32_encode_rejects_empty_oversized_and_invalid() -> None:
    """Empty, oversized, bad mode, and invalid Base32 fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_mode, content_mode, metadata_mode = _run(text="hi", mode="rot13")
    ok_bad, content_bad, metadata_bad = _run(text="!!!!", mode="decode")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "rot13"
    assert ok_bad is False and "not valid base32" in content_bad
    assert metadata_bad["mode"] == "decode"


def test_base32_encode_mentions_model_versions_as_examples() -> None:
    """Encoding stays deterministic for Gemini 3.x / Kimi K2 style payloads."""

    ok, content, metadata = _run(text="Gemini 3.x / Kimi K2", mode="encode")

    assert ok is True
    assert content == base64.b32encode(b"Gemini 3.x / Kimi K2").decode("ascii")
    assert metadata["input_chars"] == len("Gemini 3.x / Kimi K2")


def test_base32_encode_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "base32_encode" in tools
    assert tools["base32_encode"].name == "base32_encode"
    SafetyPolicy().validate_tool("base32_encode")
    assert "base32_encode" in SafetyPolicy().allowed_tools
