"""Tests for the MIME attachment filename inspection tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_attachment_names import MimeAttachmentNamesTool

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
Content-Type: text/csv; name="models.csv"
Content-Disposition: attachment

private CSV bytes
--BOUNDARY--
"""


def _run(raw: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_attachment_names tool."""

    result = MimeAttachmentNamesTool().execute(
        ToolInvocation(tool_name="mime_attachment_names", arguments={"raw": raw})
    )
    return result.ok, result.content, result.metadata


def test_mime_attachment_names_returns_filenames_without_payloads() -> None:
    """Filename and fallback name parameters are returned in MIME order."""

    ok, content, metadata = _run(_SAMPLE_MULTIPART)

    assert ok is True
    assert json.loads(content) == ["quarterly report.pdf", "models.csv"]
    assert "private GPT-5.5 body" not in content
    assert "private attachment bytes" not in content
    assert metadata["attachment_count"] == 2
    assert metadata["part_count"] == 3


def test_mime_attachment_names_decodes_encoded_filename() -> None:
    """RFC-encoded filename parameters are decoded by the email policy."""

    raw = """\
MIME-Version: 1.0
Content-Type: application/octet-stream
Content-Disposition: attachment; filename*=utf-8''caf%C3%A9.txt

payload
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == ["café.txt"]
    assert metadata["attachment_count"] == 1


def test_mime_attachment_names_returns_empty_list_when_none_are_named() -> None:
    """A valid message without named attachments succeeds with an empty list."""

    ok, content, metadata = _run("Subject: Claude Sonnet 4.6\nContent-Type: text/plain\n\nbody")

    assert ok is True
    assert json.loads(content) == []
    assert metadata["attachment_count"] == 0
    assert "body" not in content


def test_mime_attachment_names_rejects_empty_oversized_and_malformed() -> None:
    """Invalid or out-of-bounds MIME input fails structurally."""

    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run("Subject without a colon\n\nbody")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "unable to parse" in content_bad
    assert metadata_bad["defects"]


def test_mime_attachment_names_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_attachment_names" in tools
    assert tools["mime_attachment_names"].name == "mime_attachment_names"
    SafetyPolicy().validate_tool("mime_attachment_names")
    assert "mime_attachment_names" in SafetyPolicy().allowed_tools
