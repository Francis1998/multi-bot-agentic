"""Tests for the YAML → JSON conversion tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.yaml_to_json import YamlToJsonTool


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the yaml_to_json tool for a document."""

    result = YamlToJsonTool().execute(ToolInvocation(tool_name="yaml_to_json", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_yaml_to_json_converts_mapping() -> None:
    """Block YAML mappings become sorted canonical JSON."""

    ok, content, metadata = _run(
        """
models:
  - GPT-5.5
  - Claude Sonnet 4.6
enabled: true
retries: 2
"""
    )

    assert ok is True
    assert json.loads(content) == {
        "enabled": True,
        "models": ["GPT-5.5", "Claude Sonnet 4.6"],
        "retries": 2,
    }
    assert metadata["top_level_type"] == "dict"


def test_yaml_to_json_converts_sequence() -> None:
    """Top-level sequences are preserved."""

    ok, content, _metadata = _run("- Gemini 3.x\n- Kimi K2\n")

    assert ok is True
    assert json.loads(content) == ["Gemini 3.x", "Kimi K2"]


def test_yaml_to_json_rejects_empty_document() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content


def test_yaml_to_json_rejects_oversized_document() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run("a: " + ("x" * 20_000))

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] > 20_000


def test_yaml_to_json_rejects_tags_and_anchors() -> None:
    """Unsafe YAML tags/anchors outside the safe subset fail."""

    ok_tag, content_tag, _m1 = _run("value: !!str hello")
    ok_anchor, content_anchor, _m2 = _run("a: &id 1\nb: *id")

    assert ok_tag is False
    assert "invalid YAML" in content_tag
    assert ok_anchor is False
    assert "invalid YAML" in content_anchor


def test_yaml_to_json_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "yaml_to_json" in tools
    assert tools["yaml_to_json"].name == "yaml_to_json"
    SafetyPolicy().validate_tool("yaml_to_json")
    assert "yaml_to_json" in SafetyPolicy().allowed_tools
