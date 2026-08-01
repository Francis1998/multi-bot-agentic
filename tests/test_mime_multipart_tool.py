"""Tests for the MIME multipart parsing tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_multipart import MimeMultipartTool

_SAMPLE_MULTIPART = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8

Hello GPT-5.5
--BOUNDARY
Content-Type: application/json; charset=utf-8

{"model":"Kimi K2"}
--BOUNDARY--
"""


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_multipart tool with the given arguments."""

    result = MimeMultipartTool().execute(ToolInvocation(tool_name="mime_multipart", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_mime_multipart_summarizes_parts() -> None:
    """Multipart messages return JSON summaries for each payload part."""

    ok, content, metadata = _run(raw=_SAMPLE_MULTIPART)

    assert ok is True
    parts = json.loads(content)
    assert len(parts) == 2
    assert parts[0]["content_type"] == "text/plain"
    assert parts[0]["charset"] == "utf-8"
    assert "GPT-5.5" in cast(str, parts[0]["payload_preview"])
    assert parts[1]["content_type"] == "application/json"
    assert cast(int, metadata["part_count"]) == 2
    assert metadata["multipart"] is True


def test_mime_multipart_handles_single_part_message() -> None:
    """Non-multipart messages still return one part summary."""

    raw = "Content-Type: text/plain; charset=us-ascii\n\nClaude Sonnet 4.6\n"
    ok, content, metadata = _run(raw=raw)

    assert ok is True
    parts = json.loads(content)
    assert len(parts) == 1
    assert parts[0]["content_type"] == "text/plain"
    assert metadata["multipart"] is False


def test_mime_multipart_rejects_empty_raw() -> None:
    """Whitespace-only input is a structured failure."""

    ok, content, _metadata = _run(raw="   ")

    assert ok is False
    assert "empty" in content


def test_mime_multipart_rejects_oversized_raw() -> None:
    """Messages above the char cap are refused."""

    ok, content, metadata = _run(raw="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_mime_multipart_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_multipart" in tools
    assert tools["mime_multipart"].name == "mime_multipart"
    SafetyPolicy().validate_tool("mime_multipart")
    assert "mime_multipart" in SafetyPolicy().allowed_tools
