"""Tests for the rot13 tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.rot13 import Rot13Tool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the rot13 tool."""

    result = Rot13Tool().execute(ToolInvocation(tool_name="rot13", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_rot13_round_trip() -> None:
    """ROT13 is self-inverse on ASCII letters."""

    ok, content, metadata = _run(text="Hello, GPT-5.5!")
    assert ok is True and content == "Uryyb, TCG-5.5!"
    assert metadata["alphabet"] == "rot13"
    ok2, content2, _m = _run(text=content)
    assert ok2 is True and content2 == "Hello, GPT-5.5!"


def test_rot13_accepts_data_alias() -> None:
    """data argument alias works."""

    ok, content, _m = _run(data="abc")
    assert ok is True and content == "nop"


def test_rot13_preserves_non_letters() -> None:
    """Digits and punctuation are unchanged."""

    ok, content, _m = _run(text="Claude Sonnet 4.6 / Gemini 3.x")
    assert ok is True and content == "Pynhqr Fbaarg 4.6 / Trzvav 3.k"


def test_rot13_rejects_empty_missing_oversized() -> None:
    """Structural failures for empty, missing, and oversized input."""

    assert _run(text="")[0] is False
    assert _run()[0] is False
    ok_big, content_big, metadata_big = _run(text="x" * 20001)
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20001


def test_rot13_mentions_model_stack_payload() -> None:
    """Modern model stack strings remain deterministic under ROT13."""

    ok, content, metadata = _run(text="Kimi K2")
    assert ok is True and content == "Xvzv X2"
    assert metadata["input_chars"] == 7


def test_rot13_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "rot13" in tools
    assert tools["rot13"].name == "rot13"
    SafetyPolicy().validate_tool("rot13")
    assert "rot13" in SafetyPolicy().allowed_tools
