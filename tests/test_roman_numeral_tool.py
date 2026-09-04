"""Tests for the roman_numeral tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.roman_numeral import RomanNumeralTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the roman_numeral tool."""

    result = RomanNumeralTool().execute(ToolInvocation(tool_name="roman_numeral", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_roman_numeral_encode_known_values() -> None:
    """Classic values encode correctly."""

    ok, content, metadata = _run(text="1994", mode="encode")
    assert ok is True and content == "MCMXCIV"
    assert metadata["value"] == 1994
    assert isinstance(metadata["value"], int)
    ok2, content2, _m = _run(number="44")
    assert ok2 is True and content2 == "XLIV"


def test_roman_numeral_decode_round_trip() -> None:
    """decode mode reverses encode output."""

    ok, content, metadata = _run(text="MCMXCIV", mode="decode")
    assert ok is True and content == "1994"
    assert metadata["value"] == 1994
    assert isinstance(metadata["value"], int)
    ok2, content2, _m = _run(value="XLIV", mode="decode")
    assert ok2 is True and content2 == "44"


def test_roman_numeral_rejects_empty_oversized_bad_mode_range() -> None:
    """Structural failures for bad inputs and modes."""

    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="1" * 2001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 2001
    ok_mode, content_mode, metadata_mode = _run(text="12", mode="hash")
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "hash"
    ok_range, _c, metadata_range = _run(text="4000", mode="encode")
    assert ok_range is False and metadata_range["value"] == 4000


def test_roman_numeral_rejects_non_canonical_decode() -> None:
    """Non-canonical Roman strings are rejected."""

    ok, content, _m = _run(text="IIII", mode="decode")
    assert ok is False and "canonical" in content
    ok2, content2, _m2 = _run(text="ABC", mode="decode")
    assert ok2 is False and "standard" in content2


def test_roman_numeral_model_stack_label_unchanged_by_tool() -> None:
    """Tool stays deterministic for GPT-5.5-era workers."""

    ok, content, metadata = _run(text="2026")
    assert ok is True and content == "MMXXVI"
    assert metadata["mode"] == "encode"


def test_roman_numeral_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "roman_numeral" in tools
    assert tools["roman_numeral"].name == "roman_numeral"
    SafetyPolicy().validate_tool("roman_numeral")
    assert "roman_numeral" in SafetyPolicy().allowed_tools
