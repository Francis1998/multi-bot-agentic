"""Tests for the morse tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.morse import MorseTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the morse tool."""

    result = MorseTool().execute(ToolInvocation(tool_name="morse", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_morse_encode_decode_round_trip() -> None:
    """Encode then decode recovers uppercase plaintext words."""

    ok, content, metadata = _run(text="SOS HELP", mode="encode")
    assert ok is True and metadata["mode"] == "encode"
    assert content == "... --- ... / .... . .-.. .--."
    ok2, content2, metadata2 = _run(text=content, mode="decode")
    assert ok2 is True and content2 == "SOS HELP" and metadata2["mode"] == "decode"


def test_morse_rejects_unsupported_char_and_code() -> None:
    """Unsupported plaintext chars and Morse tokens fail cleanly."""

    ok, content, _m = _run(text="hi~", mode="encode")
    assert ok is False and "unsupported character" in content
    ok2, content2, _m2 = _run(text="......", mode="decode")
    assert ok2 is False and "unsupported Morse code" in content2


def test_morse_rejects_empty_missing_oversized_bad_mode() -> None:
    """Structural failures for empty, missing, oversized, and bad mode."""

    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="x" * 20001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 20001
    ok_mode, content_mode, metadata_mode = _run(text="A", mode="flip")
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "flip"


def test_morse_data_alias_and_digits() -> None:
    """data alias and digits encode deterministically."""

    ok, content, _m = _run(data="A1", mode="encode")
    assert ok is True and content == ".- .----"


def test_morse_model_stack_label() -> None:
    """Modern model names encode without network."""

    ok, content, metadata = _run(text="KIMI", mode="encode")
    assert ok is True and content == "-.- .. -- .."
    assert metadata["input_chars"] == 4


def test_morse_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "morse" in tools
    assert tools["morse"].name == "morse"
    SafetyPolicy().validate_tool("morse")
    assert "morse" in SafetyPolicy().allowed_tools
