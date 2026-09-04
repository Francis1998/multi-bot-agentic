"""Tests for the ulid tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.ulid import UlidTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the ulid tool."""

    result = UlidTool().execute(ToolInvocation(tool_name="ulid", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_ulid_generate_returns_26_crockford_chars() -> None:
    """generate mode returns a 26-char Crockford ULID."""

    ok, content, metadata = _run(mode="generate")
    assert ok is True
    assert len(content) == 26
    assert content == content.upper()
    assert metadata["length"] == 26
    assert isinstance(metadata["length"], int)
    ok2, content2, metadata2 = _run(text=content, mode="validate")
    assert ok2 is True and content2 == "true" and metadata2["valid"] is True


def test_ulid_validate_rejects_bad_shapes() -> None:
    """validate mode rejects wrong length and illegal alphabet."""

    ok, content, metadata = _run(text="not-a-ulid", mode="validate")
    assert ok is True and content == "false" and metadata["valid"] is False
    ok2, content2, metadata2 = _run(ulid="01ARZ3NDEKTSV4RRFFQ69G5FAV", mode="validate")
    assert ok2 is True and content2 == "true"
    assert isinstance(metadata2["valid"], bool)


def test_ulid_rejects_empty_oversized_bad_mode_missing() -> None:
    """Structural failures for bad inputs and modes."""

    assert _run(mode="validate")[0] is False
    assert _run(text="", mode="validate")[0] is False
    ok_big, content_big, metadata_big = _run(text="A" * 2001, mode="validate")
    assert ok_big is False and "max_chars" in content_big and metadata_big["chars"] == 2001
    ok_mode, content_mode, metadata_mode = _run(mode="hash")
    assert ok_mode is False and "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "hash"


def test_ulid_default_mode_is_generate() -> None:
    """Omitting mode defaults to generate."""

    ok, content, metadata = _run()
    assert ok is True and len(content) == 26
    assert metadata["mode"] == "generate"


def test_ulid_model_stack_label_unchanged_by_tool() -> None:
    """Tool stays deterministic-shape for GPT-5.5-era workers."""

    ok, content, metadata = _run()
    assert ok is True and len(content) == 26
    assert set(content) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert metadata["mode"] == "generate"


def test_ulid_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "ulid" in tools
    assert tools["ulid"].name == "ulid"
    SafetyPolicy().validate_tool("ulid")
    assert "ulid" in SafetyPolicy().allowed_tools
