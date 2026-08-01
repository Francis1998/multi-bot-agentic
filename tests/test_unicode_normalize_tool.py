"""Tests for the Unicode normalization tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.unicode_normalize import UnicodeNormalizeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the unicode_normalize tool with the given arguments."""

    result = UnicodeNormalizeTool().execute(ToolInvocation(tool_name="unicode_normalize", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_unicode_normalize_applies_nfc_by_default() -> None:
    """Composed NFC is the default normalization form."""

    ok, content, metadata = _run(text="caf\u00e9")

    assert ok is True
    assert content == "caf\u00e9"
    assert metadata["form"] == "NFC"
    assert cast(int, metadata["chars"]) == len("caf\u00e9")


def test_unicode_normalize_applies_nfkd() -> None:
    """NFKD decomposes compatibility characters."""

    ok, content, metadata = _run(text="\u212b", form="NFKD")

    assert ok is True
    assert content == "A\u030a"
    assert metadata["form"] == "NFKD"


def test_unicode_normalize_accepts_lowercase_form() -> None:
    """Form names are case-insensitive."""

    ok, _content, metadata = _run(text="GPT-5.5", form="nfc")

    assert ok is True
    assert metadata["form"] == "NFC"


def test_unicode_normalize_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="")

    assert ok is False
    assert "empty" in content


def test_unicode_normalize_rejects_oversized_text() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_unicode_normalize_rejects_unsupported_form() -> None:
    """Unknown normalization forms are refused."""

    ok, content, metadata = _run(text="Claude Sonnet 4.6", form="XYZ")

    assert ok is False
    assert "unsupported form" in content
    assert metadata["form"] == "XYZ"


def test_unicode_normalize_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "unicode_normalize" in tools
    assert tools["unicode_normalize"].name == "unicode_normalize"
    SafetyPolicy().validate_tool("unicode_normalize")
    assert "unicode_normalize" in SafetyPolicy().allowed_tools
