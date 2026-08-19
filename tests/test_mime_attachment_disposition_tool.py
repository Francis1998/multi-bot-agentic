"""Tests for the MIME attachment disposition inspection tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_attachment_disposition import MimeAttachmentDispositionTool

_SAMPLE_MULTIPART = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8

private GPT-5.5 body
--BOUNDARY
Content-Type: application/pdf
Content-Disposition: attachment; filename="quarterly report.pdf"

private attachment bytes
--BOUNDARY
Content-Type: image/png
Content-Disposition: inline; filename="logo.png"

private inline bytes
--BOUNDARY
Content-Type: application/octet-stream
Content-Disposition: attachment

private unnamed bytes
--BOUNDARY--
"""


def _run(raw: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_attachment_disposition tool."""

    result = MimeAttachmentDispositionTool().execute(
        ToolInvocation(tool_name="mime_attachment_disposition", arguments={"raw": raw})
    )
    return result.ok, result.content, result.metadata


def test_mime_attachment_disposition_returns_dispositions_without_payloads() -> None:
    """Disposition records retain MIME order and never include payload text."""

    ok, content, metadata = _run(_SAMPLE_MULTIPART)

    assert ok is True
    assert json.loads(content) == [
        {"filename": "quarterly report.pdf", "disposition": "attachment"},
        {"filename": "logo.png", "disposition": "inline"},
        {"filename": None, "disposition": "attachment"},
    ]
    assert "private GPT-5.5 body" not in content
    assert "private attachment bytes" not in content
    assert "private inline bytes" not in content
    assert "private unnamed bytes" not in content
    assert metadata["disposition_count"] == 3
    assert metadata["part_count"] == 4


def test_mime_attachment_disposition_decodes_encoded_filename() -> None:
    """RFC-encoded Content-Disposition filenames are decoded by stdlib email."""

    raw = """\
MIME-Version: 1.0
Content-Type: text/csv
Content-Disposition: attachment; filename*=utf-8''caf%C3%A9.csv

private Gemini 3.x payload
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == [{"filename": "café.csv", "disposition": "attachment"}]
    assert "private Gemini 3.x payload" not in content
    assert metadata["disposition_count"] == 1


def test_mime_attachment_disposition_ignores_name_without_disposition() -> None:
    """A Content-Type name alone is not Content-Disposition metadata."""

    raw = """\
MIME-Version: 1.0
Content-Type: application/json; name="Kimi K2.json"

private Claude Sonnet 4.6 payload
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == []
    assert "private Claude Sonnet 4.6 payload" not in content
    assert metadata["disposition_count"] == 0


def test_mime_attachment_disposition_rejects_empty_oversized_and_malformed() -> None:
    """Invalid or out-of-bounds MIME input fails structurally."""

    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run("Subject without a colon\n\nbody")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "unable to parse" in content_bad
    assert metadata_bad["defects"]


def test_mime_attachment_disposition_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_attachment_disposition" in tools
    assert tools["mime_attachment_disposition"].name == "mime_attachment_disposition"
    SafetyPolicy().validate_tool("mime_attachment_disposition")
    assert "mime_attachment_disposition" in SafetyPolicy().allowed_tools
