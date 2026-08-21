"""Tests for MIME attachment filename disambiguation."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_attachment_filenames_unique import MimeAttachmentFilenamesUniqueTool


def _run(raw: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_attachment_filenames_unique tool."""

    result = MimeAttachmentFilenamesUniqueTool().execute(
        ToolInvocation(tool_name="mime_attachment_filenames_unique", arguments={"raw": raw})
    )
    return result.ok, result.content, result.metadata


def _multipart(*filenames: str) -> str:
    """Build a small multipart message with named attachments."""

    parts = ["MIME-Version: 1.0", 'Content-Type: multipart/mixed; boundary="BOUNDARY"', ""]
    for filename in filenames:
        parts.extend(
            [
                "--BOUNDARY",
                "Content-Type: application/octet-stream",
                f'Content-Disposition: attachment; filename="{filename}"',
                "",
                f"private payload for {filename}",
            ]
        )
    parts.extend(["--BOUNDARY--", ""])
    return "\n".join(parts)


def test_mime_attachment_filenames_unique_disambiguates_duplicates() -> None:
    """Repeated names gain numeric suffixes before the final extension."""

    ok, content, metadata = _run(_multipart("report.pdf", "report.pdf", "report.pdf"))

    assert ok is True
    assert json.loads(content) == {
        "report.pdf": ["report.pdf", "report-2.pdf", "report-3.pdf"],
    }
    assert "private payload" not in content
    assert metadata["attachment_count"] == 3
    assert metadata["original_name_count"] == 1
    assert metadata["renamed_count"] == 2


def test_mime_attachment_filenames_unique_avoids_existing_name_collisions() -> None:
    """Generated names skip filenames already present in the message."""

    ok, content, metadata = _run(_multipart("report.pdf", "report.pdf", "report-2.pdf"))

    assert ok is True
    assert json.loads(content) == {
        "report.pdf": ["report.pdf", "report-3.pdf"],
        "report-2.pdf": ["report-2.pdf"],
    }
    assert metadata["renamed_count"] == 1


def test_mime_attachment_filenames_unique_handles_final_extensions_and_no_extension() -> None:
    """Suffixes precede only the final extension and also work without one."""

    ok, content, _metadata = _run(_multipart("archive.tar.gz", "archive.tar.gz", "README", "README"))

    assert ok is True
    assert json.loads(content) == {
        "archive.tar.gz": ["archive.tar.gz", "archive.tar-2.gz"],
        "README": ["README", "README-2"],
    }


def test_mime_attachment_filenames_unique_decodes_rfc_filename() -> None:
    """RFC-encoded names are decoded before grouping and disambiguation."""

    raw = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: application/octet-stream
Content-Disposition: attachment; filename*=utf-8''caf%C3%A9.txt

private GPT-5.5 payload
--BOUNDARY
Content-Type: application/octet-stream; name*=utf-8''caf%C3%A9.txt
Content-Disposition: attachment

private Claude Sonnet 4.6 payload
--BOUNDARY--
"""
    ok, content, metadata = _run(raw)

    assert ok is True
    assert json.loads(content) == {"café.txt": ["café.txt", "café-2.txt"]}
    assert "private" not in content
    assert metadata["attachment_count"] == 2


def test_mime_attachment_filenames_unique_returns_empty_mapping_without_names() -> None:
    """A valid message without named attachments succeeds with an empty object."""

    ok, content, metadata = _run("Subject: Gemini 3.x\nContent-Type: text/plain\n\nKimi K2 body")

    assert ok is True
    assert json.loads(content) == {}
    assert metadata["attachment_count"] == 0
    assert "Kimi K2 body" not in content


def test_mime_attachment_filenames_unique_rejects_invalid_input() -> None:
    """Empty, oversized, and defective raw MIME fail safely."""

    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run("Subject without a colon\n\nbody")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "unable to parse" in content_bad
    assert metadata_bad["defects"]


def test_mime_attachment_filenames_unique_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_attachment_filenames_unique" in tools
    assert tools["mime_attachment_filenames_unique"].name == "mime_attachment_filenames_unique"
    SafetyPolicy().validate_tool("mime_attachment_filenames_unique")
    assert "mime_attachment_filenames_unique" in SafetyPolicy().allowed_tools
