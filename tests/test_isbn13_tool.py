"""Tests for the isbn13 tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.isbn13 import Isbn13Tool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the isbn13 tool."""

    result = Isbn13Tool().execute(ToolInvocation(tool_name="isbn13", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_isbn13_validate_known_isbn() -> None:
    """Known ISBN-13 validates; corrupted digit fails."""

    ok, content, metadata = _run(text="978-0-306-40615-7", mode="validate")
    assert ok is True and content == "true"
    assert metadata["valid"] is True
    assert isinstance(metadata["valid"], bool)
    ok2, content2, metadata2 = _run(isbn="9780306406158", mode="validate")
    assert ok2 is True and content2 == "false" and metadata2["valid"] is False


def test_isbn13_check_digit_completes_valid_number() -> None:
    """check_digit mode appends a digit that validates."""

    ok, content, metadata = _run(text="978030640615", mode="check_digit")
    assert ok is True and content == "9780306406157"
    assert metadata["check_digit"] == 7
    assert isinstance(metadata["check_digit"], int)
    ok2, content2, _m = _run(text=content, mode="validate")
    assert ok2 is True and content2 == "true"


def test_isbn13_rejects_non_digits_empty_oversized_bad_mode() -> None:
    """Structural failures for bad characters and modes."""

    assert _run(text="978a")[0] is False
    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="1" * 2001)
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 2001
    ok_mode, content_mode, metadata_mode = _run(text="12", mode="hash")
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "hash"


def test_isbn13_wrong_length_invalid() -> None:
    """Non-13-digit validate returns false; check_digit needs 12 digits."""

    ok, content, metadata = _run(text="978030640615", mode="validate")
    assert ok is True and content == "false" and metadata["valid"] is False
    ok2, _c2, metadata2 = _run(text="9780306406157", mode="check_digit")
    assert ok2 is False and metadata2["digits"] == 13


def test_isbn13_model_stack_label_unchanged_by_tool() -> None:
    """Tool stays deterministic for GPT-5.5-era workers."""

    ok, content, metadata = _run(text="9780143127741")
    assert ok is True and content == "true"
    assert metadata["mode"] == "validate"


def test_isbn13_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "isbn13" in tools
    assert tools["isbn13"].name == "isbn13"
    SafetyPolicy().validate_tool("isbn13")
    assert "isbn13" in SafetyPolicy().allowed_tools
