"""Tests for the punycode tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.punycode import PunycodeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the punycode tool."""

    result = PunycodeTool().execute(ToolInvocation(tool_name="punycode", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_punycode_encodes_unicode_domain() -> None:
    """Unicode labels encode to xn-- Punycode."""

    ok, content, metadata = _run(text="münchen.de")
    assert ok is True
    assert content.startswith("xn--") or "xn--" in content
    assert content.endswith(".de")
    assert metadata["mode"] == "encode"


def test_punycode_round_trips() -> None:
    """Decode recovers the original Unicode domain."""

    original = "bücher.example"
    ok_enc, encoded, _m = _run(domain=original, mode="encode")
    assert ok_enc is True
    ok, content, metadata = _run(text=encoded, mode="decode")
    assert ok is True
    assert content == original
    assert metadata["mode"] == "decode"


def test_punycode_ascii_identity_encode() -> None:
    """ASCII domains encode to themselves."""

    ok, content, metadata = _run(text="example.com")
    assert ok is True
    assert content == "example.com"
    assert metadata["mode"] == "encode"


def test_punycode_rejects_empty_oversized_bad_mode_invalid() -> None:
    """Structural and codec failures."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 2001)
    ok_mode, content_mode, metadata_mode = _run(text="a.com", mode="rot13")
    ok_bad, content_bad, metadata_bad = _run(text="xn--!!!", mode="decode")
    ok_missing, content_missing, _m2 = _run()

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 2001
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "rot13"
    assert ok_bad is False and "failed" in content_bad
    assert metadata_bad["mode"] == "decode"
    assert ok_missing is False and "missing required argument" in content_missing


def test_punycode_mentions_model_stack_payload() -> None:
    """Encoding stays deterministic for model-stack style labels."""

    ok, content, metadata = _run(text="gpt.example")
    assert ok is True
    assert content == "gpt.example"
    assert metadata["input_chars"] == len("gpt.example")


def test_punycode_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "punycode" in tools
    assert tools["punycode"].name == "punycode"
    SafetyPolicy().validate_tool("punycode")
    assert "punycode" in SafetyPolicy().allowed_tools
