"""Tests for the base85 tool."""

from __future__ import annotations

import base64
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.base85 import Base85Tool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the base85 tool."""

    result = Base85Tool().execute(ToolInvocation(tool_name="base85", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_base85_encodes_utf8_by_default() -> None:
    """Default mode encodes UTF-8 text to ASCII85."""

    text = "hello"
    expected = base64.a85encode(text.encode()).decode("ascii")
    ok, content, metadata = _run(text=text)
    assert ok is True
    assert content == expected
    assert metadata["mode"] == "encode"
    assert metadata["alphabet"] == "ascii85"


def test_base85_accepts_data_alias_and_round_trips() -> None:
    """``data`` is accepted; decode recovers the original UTF-8 text."""

    text = "GPT-5.5 / Claude Sonnet 4.6"
    ok_enc, encoded, _meta_enc = _run(data=text, mode="encode")
    assert ok_enc is True
    ok, content, metadata = _run(text=encoded, mode="decode")
    assert ok is True
    assert content == text
    assert metadata["mode"] == "decode"


def test_base85_handles_whitespace_on_decode() -> None:
    """Whitespace inside Base85 input is ignored on decode."""

    text = "Gemini 3.x / Kimi K2"
    encoded = base64.a85encode(text.encode()).decode("ascii")
    spaced = " ".join(encoded[i : i + 4] for i in range(0, len(encoded), 4))
    ok, content, metadata = _run(text=spaced, mode="decode")
    assert ok is True
    assert content == text
    assert metadata["alphabet"] == "ascii85"


def test_base85_rejects_empty_oversized_and_invalid() -> None:
    """Empty, oversized, bad mode, and invalid Base85 fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_mode, content_mode, metadata_mode = _run(text="hi", mode="rot13")
    ok_bad, content_bad, metadata_bad = _run(text="~~~~", mode="decode")
    ok_missing, content_missing, _m2 = _run()

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "rot13"
    assert ok_bad is False and "failed" in content_bad
    assert metadata_bad["mode"] == "decode"
    assert ok_missing is False and "missing required argument" in content_missing


def test_base85_mentions_model_versions_as_examples() -> None:
    """Encoding stays deterministic for modern model-stack payloads."""

    ok, content, metadata = _run(text="Gemini 3.x / Kimi K2", mode="encode")
    assert ok is True
    assert content == base64.a85encode(b"Gemini 3.x / Kimi K2").decode("ascii")
    assert metadata["input_chars"] == len("Gemini 3.x / Kimi K2")


def test_base85_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "base85" in tools
    assert tools["base85"].name == "base85"
    SafetyPolicy().validate_tool("base85")
    assert "base85" in SafetyPolicy().allowed_tools
