"""Tests for the iban_check tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.iban_check import IbanCheckTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the iban_check tool."""

    result = IbanCheckTool().execute(ToolInvocation(tool_name="iban_check", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_valid_gb_iban() -> None:
    """Known valid GB IBAN passes mod-97."""

    ok, content, metadata = _run(iban="GB29 NWBK 6016 1331 9268 19")
    assert ok is True and content == "valid"
    assert metadata["valid"] is True
    assert isinstance(metadata["valid"], bool)
    assert metadata["country"] == "GB"


def test_valid_de_iban() -> None:
    """Known valid DE IBAN."""

    ok, content, metadata = _run(iban="DE89370400440532013000")
    assert ok is True and content == "valid"
    assert metadata["country"] == "DE"


def test_invalid_iban_bad_checksum() -> None:
    """Corrupted check digits fail."""

    ok, content, metadata = _run(iban="GB00 NWBK 6016 1331 9268 19")
    assert ok is True and content == "invalid"
    assert metadata["valid"] is False


def test_accepts_text_argument() -> None:
    """The tool also accepts 'text' as the argument name."""

    ok, content, _m = _run(text="DE89370400440532013000")
    assert ok is True and content == "valid"


def test_rejects_empty_missing_short_long() -> None:
    """Structural failures."""

    assert _run(iban="")[0] is False
    assert _run()[0] is False
    ok_short, content_short, _m = _run(iban="GB29NWBK601613")
    assert ok_short is False and "length" in content_short
    ok_long, content_long, _m = _run(iban="GB29NWBK6016133192681900000000000000000")
    assert ok_long is False and "length" in content_long


def test_rejects_bad_country_and_check_digits() -> None:
    """Non-alpha country code and non-digit check positions fail."""

    ok1, content1, _m = _run(iban="12NWBK601613319268190")
    assert ok1 is False and "country code" in content1
    ok2, content2, _m = _run(iban="GBXX NWBK 6016 1331 9268 19")
    assert ok2 is False and "check digits" in content2


def test_iban_check_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "iban_check" in tools
    assert tools["iban_check"].name == "iban_check"
    SafetyPolicy().validate_tool("iban_check")
    assert "iban_check" in SafetyPolicy().allowed_tools
