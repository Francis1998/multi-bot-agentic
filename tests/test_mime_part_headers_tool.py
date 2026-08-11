"""Tests for the MIME part header inspection tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.mime_part_headers import MimePartHeadersTool

_SAMPLE_MULTIPART = """\
From: Ada <ada@example.com>
Subject: Model handoff
X-Trace: first
X-Trace: second
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8
Content-Language: en

secret GPT-5.5 body
--BOUNDARY
Content-Type: text/html; charset=utf-8

<p>secret Kimi K2 body</p>
--BOUNDARY--
"""


def _run(raw: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the mime_part_headers tool."""

    result = MimePartHeadersTool().execute(ToolInvocation(tool_name="mime_part_headers", arguments={"raw": raw}))
    return result.ok, result.content, result.metadata


def test_mime_part_headers_returns_top_level_and_part_maps_only() -> None:
    """The JSON contains decoded header maps but no body payload."""

    ok, content, metadata = _run(_SAMPLE_MULTIPART)

    assert ok is True
    document = json.loads(content)
    assert document["top_level"]["From"] == "Ada <ada@example.com>"
    assert document["top_level"]["Subject"] == "Model handoff"
    assert document["top_level"]["X-Trace"] == ["first", "second"]
    assert document["parts"][0] == {
        "index": 1,
        "headers": {
            "Content-Language": "en",
            "Content-Type": 'text/plain; charset="utf-8"',
        },
    }
    assert document["parts"][1]["headers"]["Content-Type"] == 'text/html; charset="utf-8"'
    assert "secret GPT-5.5 body" not in content
    assert "secret Kimi K2 body" not in content
    assert metadata["part_count"] == 2
    assert cast(int, metadata["top_level_header_count"]) >= 5


def test_mime_part_headers_handles_single_part_message() -> None:
    """A single-part message has top-level headers and no child parts."""

    ok, content, metadata = _run("Subject: Claude Sonnet 4.6\nContent-Type: text/plain\n\nbody")

    assert ok is True
    document = json.loads(content)
    assert document["top_level"]["Subject"] == "Claude Sonnet 4.6"
    assert document["parts"] == []
    assert metadata["part_count"] == 0
    assert "body" not in content


def test_mime_part_headers_rejects_empty_oversized_and_malformed() -> None:
    """Invalid or out-of-bounds raw messages fail structurally."""

    ok_empty, content_empty, _m1 = _run("   ")
    ok_big, content_big, metadata_big = _run("x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run("Subject without a colon\n\nbody")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "unable to parse" in content_bad
    assert metadata_bad["defects"]


def test_mime_part_headers_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "mime_part_headers" in tools
    assert tools["mime_part_headers"].name == "mime_part_headers"
    SafetyPolicy().validate_tool("mime_part_headers")
    assert "mime_part_headers" in SafetyPolicy().allowed_tools
