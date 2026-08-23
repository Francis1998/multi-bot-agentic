"""Tests for the MIME multipart flatten tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_multipart_flatten import MimeMultipartFlattenTool

_NESTED_MIME = """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=OUTER

--OUTER
Content-Type: multipart/alternative; boundary=INNER

--INNER
Content-Type: text/plain; charset=utf-8

GPT-5.5 summary
--INNER
Content-Type: text/html; charset=utf-8

<p>Claude Sonnet 4.6</p>
--INNER--
--OUTER
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"
Content-ID: <report@cid>

JVBERi0=
--OUTER--
"""


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_multipart_flatten tool."""

    result = MimeMultipartFlattenTool().execute(
        ToolInvocation(tool_name="mime_multipart_flatten", arguments=dict(arguments))
    )
    return result.ok, result.content, result.metadata


def test_mime_multipart_flatten_returns_leaf_metadata() -> None:
    """Nested multipart messages flatten to leaf metadata without payloads."""

    ok, content, metadata = _run(raw=_NESTED_MIME)

    assert ok is True
    parts = json.loads(content)
    assert len(parts) == 3
    assert parts[0]["content_type"] == "text/plain"
    assert parts[1]["content_type"] == "text/html"
    assert parts[2]["filename"] == "report.pdf"
    assert parts[2]["content_id"] == "<report@cid>"
    assert "JVBERi0=" not in content
    assert metadata["parts"] == 3
    max_depth = metadata["max_depth"]
    assert isinstance(max_depth, int)
    assert max_depth >= 1


def test_mime_multipart_flatten_handles_single_part() -> None:
    """A non-multipart message yields one depth-0 leaf."""

    raw = "Content-Type: text/plain\n\nGemini 3.x\n"
    ok, content, metadata = _run(raw=raw)
    assert ok is True
    parts = json.loads(content)
    assert parts == [
        {
            "content_type": "text/plain",
            "filename": "",
            "content_id": "",
            "size": len(b"Gemini 3.x\n"),
            "depth": 0,
        }
    ]
    assert metadata["parts"] == 1


def test_mime_multipart_flatten_rejects_empty_and_oversized() -> None:
    """Empty and oversized MIME inputs fail safely."""

    ok_empty, content_empty, _m1 = _run(raw="   ")
    ok_big, content_big, meta = _run(raw="x" * 20_001)

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big and meta["chars"] == 20_001


def test_mime_multipart_flatten_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_multipart_flatten" in tools
    assert tools["mime_multipart_flatten"].name == "mime_multipart_flatten"
    SafetyPolicy().validate_tool("mime_multipart_flatten")
    assert "mime_multipart_flatten" in SafetyPolicy().allowed_tools
