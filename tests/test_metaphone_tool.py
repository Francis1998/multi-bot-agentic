"""Tests for the metaphone tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.metaphone import MetaphoneTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the metaphone tool."""

    result = MetaphoneTool().execute(ToolInvocation(tool_name="metaphone", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_metaphone_joseph_variants_match() -> None:
    """Joseph and Jawsef share classic Metaphone JSF."""

    ok_joseph, content_joseph, metadata_joseph = _run(text="Joseph")
    ok_jawsef, content_jawsef, _metadata = _run(text="Jawsef")

    assert ok_joseph is True
    assert content_joseph == "JSF"
    assert metadata_joseph["metaphone"] == "JSF"
    assert metadata_joseph["algorithm"] == "classic"
    assert ok_jawsef is True
    assert content_jawsef == "JSF"


def test_metaphone_catherine_and_katherine_match() -> None:
    """Catherine and Katherine both encode to K0RN."""

    ok_c, content_c, _m1 = _run(text="Catherine")
    ok_k, content_k, _m2 = _run(text="Katherine")

    assert ok_c is True
    assert content_c == "K0RN"
    assert ok_k is True
    assert content_k == "K0RN"


def test_metaphone_canonical_examples() -> None:
    """Additional canonical classic Metaphone examples."""

    ok, content, _metadata = _run(text="Smith")
    assert ok is True
    assert content == "SM0"

    ok_s, content_s, _metadata_s = _run(text="Schmidt")
    assert ok_s is True
    assert content_s == "SXMTT"

    ok_w, content_w, _metadata_w = _run(text="White")
    assert ok_w is True
    assert content_w == "WT"


def test_metaphone_rejects_missing_and_empty_text() -> None:
    """Missing or empty text fails structurally."""

    ok_missing, content_missing, _metadata = _run()
    ok_empty, content_empty, _metadata2 = _run(text="")

    assert ok_missing is False
    assert "missing required argument" in content_missing
    assert ok_empty is False
    assert "empty" in content_empty


def test_metaphone_rejects_oversized_input() -> None:
    """Inputs over 2000 chars fail."""

    ok, content, metadata = _run(text="a" * 2001)
    assert ok is False
    assert "exceeds max" in content
    assert metadata["chars"] == 2001


def test_metaphone_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "metaphone" in tools
    assert tools["metaphone"].name == "metaphone"
    SafetyPolicy().validate_tool("metaphone")
    assert "metaphone" in SafetyPolicy().allowed_tools
