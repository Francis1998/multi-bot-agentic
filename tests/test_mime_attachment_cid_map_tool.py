"""Tests for the MIME Content-ID attachment map tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_attachment_cid_map import MimeAttachmentCidMapTool

_SAMPLE_MULTIPART = """\
MIME-Version: 1.0
Content-Type: multipart/related; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/html; charset=utf-8

<img src="cid:logo@gpt55">
--BOUNDARY
Content-Type: image/png
Content-ID: <logo@gpt55>
Content-Disposition: inline; filename="logo.png"

private PNG bytes
--BOUNDARY
Content-Type: application/pdf
Content-ID: <report@claude46>
Content-Disposition: attachment; filename="report.pdf"

private PDF bytes
--BOUNDARY--
"""


def _run(raw: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_attachment_cid_map tool."""

    result = MimeAttachmentCidMapTool().execute(
        ToolInvocation(tool_name="mime_attachment_cid_map", arguments={"raw": raw})
    )
    return result.ok, result.content, result.metadata


def test_mime_attachment_cid_map_returns_cid_metadata_without_payloads() -> None:
    """Content-ID tokens map to filename/content_type without payload bytes."""

    ok, content, metadata = _run(_SAMPLE_MULTIPART)

    assert ok is True
    assert json.loads(content) == {
        "logo@gpt55": {"content_type": "image/png", "filename": "logo.png"},
        "report@claude46": {"content_type": "application/pdf", "filename": "report.pdf"},
    }
    assert "private PNG bytes" not in content
    assert "private PDF bytes" not in content
    assert "<img" not in content
    assert metadata["mapped_count"] == 2
    assert metadata["part_count"] == 3


def test_mime_attachment_cid_map_handles_missing_filename_and_content_type() -> None:
    """Missing filename becomes empty; missing Content-Type defaults safely."""

    raw = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="B"

--B
Content-ID: <gemini3x@example>

payload
--B--
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == {
        "gemini3x@example": {
            "content_type": "application/octet-stream",
            "filename": "",
        }
    }
    assert metadata["mapped_count"] == 1
    assert "payload" not in content


def test_mime_attachment_cid_map_returns_empty_object_when_no_cids() -> None:
    """A valid message without Content-ID headers succeeds with an empty map."""

    ok, content, metadata = _run("Subject: Kimi K2\nContent-Type: text/plain\n\nbody")

    assert ok is True
    assert json.loads(content) == {}
    assert metadata["mapped_count"] == 0
    assert "body" not in content


def test_mime_attachment_cid_map_rejects_duplicates_and_invalid_input() -> None:
    """Duplicate CIDs and empty/oversized/malformed input fail structurally."""

    duplicate = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="B"

--B
Content-ID: <same@id>
Content-Disposition: attachment; filename="a.txt"

a
--B
Content-ID: <same@id>
Content-Disposition: attachment; filename="b.txt"

b
--B--
"""
    ok_dup, content_dup, metadata_dup = _run(duplicate)
    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run("Subject without a colon\n\nbody")

    assert ok_dup is False and "duplicate Content-ID" in content_dup
    assert metadata_dup["cid"] == "same@id"
    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "unable to parse" in content_bad
    assert metadata_bad["defects"]


def test_mime_attachment_cid_map_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_attachment_cid_map" in tools
    assert tools["mime_attachment_cid_map"].name == "mime_attachment_cid_map"
    SafetyPolicy().validate_tool("mime_attachment_cid_map")
    assert "mime_attachment_cid_map" in SafetyPolicy().allowed_tools
