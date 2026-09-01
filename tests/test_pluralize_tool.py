"""Tests for the pluralize tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.pluralize import PluralizeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the pluralize tool."""

    result = PluralizeTool().execute(ToolInvocation(tool_name="pluralize", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_pluralize_regular_and_irregular() -> None:
    """Regular and irregular plurals are deterministic."""

    ok, content, metadata = _run(text="cat")
    assert ok is True and content == "cats" and metadata["mode"] == "pluralize"
    ok2, content2, _m = _run(word="child")
    assert ok2 is True and content2 == "children"
    ok3, content3, _m3 = _run(text="Analysis", mode="pluralize")
    assert ok3 is True and content3 == "Analyses"


def test_pluralize_singularize_round_trip_common() -> None:
    """Singularize recovers common plurals."""

    ok, content, metadata = _run(text="boxes", mode="singularize")
    assert ok is True and content == "box" and metadata["mode"] == "singularize"
    ok2, content2, _m = _run(text="people", mode="singularize")
    assert ok2 is True and content2 == "person"


def test_pluralize_y_and_f_rules() -> None:
    """Consonant-y and -f/-fe rules apply."""

    assert _run(text="city")[1] == "cities"
    assert _run(text="leaf")[1] == "leaves"
    assert _run(text="knife")[1] == "knives"


def test_pluralize_rejects_empty_multiword_oversized_bad_mode() -> None:
    """Structural failures for empty, multi-word, oversized, and bad mode."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_multi, content_multi, _m2 = _run(text="two words")
    ok_big, content_big, metadata_big = _run(text="x" * 2001)
    ok_mode, content_mode, metadata_mode = _run(text="cat", mode="dual")
    ok_missing, content_missing, _m3 = _run()

    assert ok_empty is False and "empty" in content_empty
    assert ok_multi is False and "single word" in content_multi
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 2001
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "dual"
    assert ok_missing is False and "missing required argument" in content_missing


def test_pluralize_mentions_model_stack() -> None:
    """Payload mentioning modern model stack stays deterministic."""

    ok, content, metadata = _run(text="model")
    assert ok is True and content == "models"
    assert metadata["input"] == "model"


def test_pluralize_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "pluralize" in tools
    assert tools["pluralize"].name == "pluralize"
    SafetyPolicy().validate_tool("pluralize")
    assert "pluralize" in SafetyPolicy().allowed_tools
