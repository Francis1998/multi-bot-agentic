"""Tests for the soundex tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.soundex import SoundexTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the soundex tool."""

    result = SoundexTool().execute(ToolInvocation(tool_name="soundex", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_soundex_robert_and_rupert_match() -> None:
    """Robert and Rupert share Soundex R163."""

    ok_robert, content_robert, metadata_robert = _run(text="Robert")
    ok_rupert, content_rupert, _metadata_rupert = _run(text="Rupert")

    assert ok_robert is True
    assert content_robert == "R163"
    assert metadata_robert["soundex"] == "R163"
    assert ok_rupert is True
    assert content_rupert == "R163"


def test_soundex_ashcraft_variants() -> None:
    """Ashcraft and Ashcroft both encode to A261 (H/W separation rule)."""

    ok_craft, content_craft, _metadata = _run(text="Ashcraft")
    ok_croft, content_croft, _metadata2 = _run(text="Ashcroft")

    assert ok_craft is True
    assert content_craft == "A261"
    assert ok_croft is True
    assert content_croft == "A261"


def test_soundex_tymczak_and_washington() -> None:
    """Additional canonical Soundex examples."""

    ok, content, _metadata = _run(text="Tymczak")
    assert ok is True
    assert content == "T522"

    ok_w, content_w, _metadata_w = _run(text="Washington")
    assert ok_w is True
    assert content_w == "W252"


def test_soundex_rejects_missing_and_empty_text() -> None:
    """Missing or empty text fails structurally."""

    ok_missing, content_missing, _metadata = _run()
    ok_empty, content_empty, _metadata2 = _run(text="")

    assert ok_missing is False
    assert "missing required argument" in content_missing
    assert ok_empty is False
    assert "empty" in content_empty


def test_soundex_rejects_oversized_input() -> None:
    """Inputs over 2000 chars fail."""

    ok, content, metadata = _run(text="a" * 2001)
    assert ok is False
    assert "exceeds max" in content
    assert metadata["chars"] == 2001


def test_soundex_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "soundex" in tools
    assert tools["soundex"].name == "soundex"
    SafetyPolicy().validate_tool("soundex")
    assert "soundex" in SafetyPolicy().allowed_tools
