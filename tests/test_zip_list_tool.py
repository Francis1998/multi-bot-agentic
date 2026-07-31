"""Tests for the ZIP archive listing tool."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.zip_list import ZipListTool


def _encode_zip(*entries: tuple[str, str]) -> str:
    """Build a small ZIP archive and return its base64 encoding."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the zip_list tool for a base64 payload."""

    result = ZipListTool().execute(ToolInvocation(tool_name="zip_list", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_zip_list_returns_member_metadata() -> None:
    """Valid ZIP payloads list member metadata as JSON."""

    encoded = _encode_zip(
        ("models/gpt-5.5.txt", "GPT-5.5"),
        ("models/claude-sonnet-4.6.txt", "Claude Sonnet 4.6"),
    )

    ok, content, metadata = _run(encoded)

    assert ok is True
    parsed = json.loads(content)
    assert parsed == [
        {
            "name": "models/claude-sonnet-4.6.txt",
            "size": len("Claude Sonnet 4.6"),
            "compress_size": parsed[0]["compress_size"],
            "date": parsed[0]["date"],
        },
        {
            "name": "models/gpt-5.5.txt",
            "size": len("GPT-5.5"),
            "compress_size": parsed[1]["compress_size"],
            "date": parsed[1]["date"],
        },
    ]
    assert metadata["member_count"] == 2


def test_zip_list_rejects_non_zip_payload() -> None:
    """Non-ZIP base64 payloads return a structured failure."""

    encoded = base64.b64encode(b"not-a-zip").decode("ascii")
    ok, content, _metadata = _run(encoded)

    assert ok is False
    assert "not a valid zip" in content


def test_zip_list_rejects_empty_document() -> None:
    """Whitespace-only input is a structured failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content


def test_zip_list_rejects_oversized_base64() -> None:
    """Base64 payloads above the char cap are refused."""

    ok, content, metadata = _run("A" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_zip_list_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "zip_list" in tools
    assert tools["zip_list"].name == "zip_list"
    SafetyPolicy().validate_tool("zip_list")
    assert "zip_list" in SafetyPolicy().allowed_tools
