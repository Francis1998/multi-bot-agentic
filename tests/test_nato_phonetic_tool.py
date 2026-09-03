"""Tests for the nato_phonetic tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.nato_phonetic import NatoPhoneticTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the nato_phonetic tool."""

    result = NatoPhoneticTool().execute(ToolInvocation(tool_name="nato_phonetic", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_encode_simple_word() -> None:
    """Encode a simple word to NATO phonetic."""

    ok, content, metadata = _run(text="SOS")
    assert ok is True
    assert content == "Sierra Oscar Sierra"
    assert metadata["mode"] == "encode"


def test_encode_with_non_alpha_passthrough() -> None:
    """Non-alpha characters pass through."""

    ok, content, _m = _run(text="A-1")
    assert ok is True
    assert content == "Alfa - One"


def test_decode_phonetic_words() -> None:
    """Decode NATO phonetic words back to text."""

    ok, content, metadata = _run(text="Alfa Bravo Charlie", mode="decode")
    assert ok is True
    assert content == "ABC"
    assert metadata["mode"] == "decode"


def test_decode_unknown_words_passthrough() -> None:
    """Unknown words in decode mode pass through."""

    ok, content, _m = _run(text="Alfa ?? Bravo", mode="decode")
    assert ok is True
    assert content == "A??B"


def test_rejects_empty_missing_oversized_bad_mode() -> None:
    """Structural failures."""

    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="A" * 2001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 2001
    ok_mode, content_mode, _m = _run(text="hi", mode="reverse")
    assert ok_mode is False and "unsupported mode" in content_mode


def test_encode_digits() -> None:
    """Digits map to NATO digit words."""

    ok, content, _m = _run(text="42")
    assert ok is True
    assert content == "Four Two"


def test_nato_phonetic_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "nato_phonetic" in tools
    assert tools["nato_phonetic"].name == "nato_phonetic"
    SafetyPolicy().validate_tool("nato_phonetic")
    assert "nato_phonetic" in SafetyPolicy().allowed_tools
