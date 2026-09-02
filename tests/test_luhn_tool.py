"""Tests for the luhn tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.luhn import LuhnTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the luhn tool."""

    result = LuhnTool().execute(ToolInvocation(tool_name="luhn", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_luhn_validate_known_pan() -> None:
    """Classic test PAN validates; corrupted digit fails."""

    ok, content, metadata = _run(text="4111 1111 1111 1111", mode="validate")
    assert ok is True and content == "true"
    assert metadata["valid"] is True
    assert isinstance(metadata["valid"], bool)
    ok2, content2, metadata2 = _run(number="4111111111111112", mode="validate")
    assert ok2 is True and content2 == "false" and metadata2["valid"] is False


def test_luhn_check_digit_completes_valid_number() -> None:
    """check_digit mode appends a digit that validates."""

    ok, content, metadata = _run(text="7992739871", mode="check_digit")
    assert ok is True and content == "79927398713"
    assert metadata["check_digit"] == 3
    assert isinstance(metadata["check_digit"], int)
    ok2, content2, _m = _run(text=content, mode="validate")
    assert ok2 is True and content2 == "true"


def test_luhn_rejects_non_digits_empty_oversized_bad_mode() -> None:
    """Structural failures for bad characters and modes."""

    assert _run(text="12a3")[0] is False
    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="1" * 2001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 2001
    ok_mode, content_mode, metadata_mode = _run(text="12", mode="hash")
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "hash"


def test_luhn_short_numbers_invalid() -> None:
    """Single-digit strings are not Luhn-valid."""

    ok, content, metadata = _run(text="7", mode="validate")
    assert ok is True and content == "false" and metadata["valid"] is False


def test_luhn_model_stack_label_unchanged_by_tool() -> None:
    """Tool stays deterministic for GPT-5.5-era workers."""

    ok, content, metadata = _run(text="4242424242424242")
    assert ok is True and content == "true"
    assert metadata["mode"] == "validate"


def test_luhn_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "luhn" in tools
    assert tools["luhn"].name == "luhn"
    SafetyPolicy().validate_tool("luhn")
    assert "luhn" in SafetyPolicy().allowed_tools
