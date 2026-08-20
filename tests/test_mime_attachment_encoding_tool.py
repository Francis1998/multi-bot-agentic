"""Tests for the MIME attachment transfer-encoding inspection tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_attachment_encoding import MimeAttachmentEncodingTool

_SAMPLE_MULTIPART = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: quoted-printable

private GPT-5.5 body
--BOUNDARY
Content-Type: application/pdf
Content-Disposition: attachment; filename="quarterly report.pdf"
Content-Transfer-Encoding: BASE64

private attachment bytes
--BOUNDARY
Content-Type: text/csv; name="models.csv"
Content-Transfer-Encoding: quoted-printable

private Gemini 3.x bytes
--BOUNDARY
Content-Type: application/octet-stream
Content-Disposition: attachment
Content-Transfer-Encoding: 8bit

private unnamed bytes
--BOUNDARY--
"""


def _run(raw: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_attachment_encoding tool."""

    result = MimeAttachmentEncodingTool().execute(
        ToolInvocation(tool_name="mime_attachment_encoding", arguments={"raw": raw})
    )
    return result.ok, result.content, result.metadata


def test_mime_attachment_encoding_returns_encodings_without_payloads() -> None:
    """Named-part encodings retain MIME order without exposing payloads."""

    ok, content, metadata = _run(_SAMPLE_MULTIPART)

    assert ok is True
    assert json.loads(content) == [
        {"filename": "quarterly report.pdf", "encoding": "base64"},
        {"filename": "models.csv", "encoding": "quoted-printable"},
    ]
    assert "private GPT-5.5 body" not in content
    assert "private attachment bytes" not in content
    assert "private Gemini 3.x bytes" not in content
    assert "private unnamed bytes" not in content
    assert metadata["attachment_count"] == 2
    assert metadata["part_count"] == 4


def test_mime_attachment_encoding_decodes_filename_and_defaults_to_7bit() -> None:
    """Encoded filenames are decoded and missing transfer encoding uses 7bit."""

    raw = """\
MIME-Version: 1.0
Content-Type: application/json; name*=utf-8''caf%C3%A9.json
Content-Disposition: attachment

private Claude Sonnet 4.6 payload
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == [{"filename": "café.json", "encoding": "7bit"}]
    assert "private Claude Sonnet 4.6 payload" not in content
    assert metadata["attachment_count"] == 1


def test_mime_attachment_encoding_accepts_named_inline_parts() -> None:
    """A named inline MIME part is attachment metadata like sibling tools."""

    raw = """\
MIME-Version: 1.0
Content-Type: image/png
Content-Disposition: inline; filename="Kimi K2.png"
Content-Transfer-Encoding: binary

private image bytes
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == [{"filename": "Kimi K2.png", "encoding": "binary"}]
    assert metadata["attachment_count"] == 1
    assert "private image bytes" not in content


def test_mime_attachment_encoding_returns_empty_list_without_named_parts() -> None:
    """A valid message without named parts returns an empty JSON list."""

    ok, content, metadata = _run(
        "Subject: Gemini 3.x\nContent-Type: text/plain\nContent-Transfer-Encoding: 8bit\n\nbody"
    )

    assert ok is True
    assert json.loads(content) == []
    assert metadata["attachment_count"] == 0
    assert "body" not in content


def test_mime_attachment_encoding_rejects_empty_oversized_and_malformed() -> None:
    """Invalid and out-of-bounds MIME inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run("Subject without a colon\n\nbody")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "unable to parse" in content_bad
    assert metadata_bad["defects"]


def test_mime_attachment_encoding_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_attachment_encoding" in tools
    assert tools["mime_attachment_encoding"].name == "mime_attachment_encoding"
    SafetyPolicy().validate_tool("mime_attachment_encoding")
    assert "mime_attachment_encoding" in SafetyPolicy().allowed_tools
