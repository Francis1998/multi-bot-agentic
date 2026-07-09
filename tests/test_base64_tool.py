"""Tests for the Base64 encode/decode tool."""

from __future__ import annotations

import base64

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.base64_codec import Base64Tool


def _run(text: str, operation: str | None = None) -> tuple[bool, str, dict[str, object]]:
    """Execute the base64 tool for a document.

    Args:
        text: Document text to transform.
        operation: Optional operation to request (``encode`` or ``decode``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text}
    if operation is not None:
        arguments["operation"] = operation
    result = Base64Tool().execute(ToolInvocation(tool_name="base64", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_base64_defaults_to_encode() -> None:
    """Without an operation argument the tool encodes to standard Base64."""

    ok, content, metadata = _run("hello world")

    assert ok is True
    assert content == base64.b64encode(b"hello world").decode("ascii")
    assert metadata["operation"] == "encode"


def test_base64_round_trips_unicode() -> None:
    """Encoding then decoding returns the original UTF-8 document."""

    encoded_ok, encoded, _meta = _run("café ☕", operation="encode")
    decoded_ok, decoded, _decoded_meta = _run(encoded, operation="decode")

    assert encoded_ok is True and decoded_ok is True
    assert decoded == "café ☕"


def test_base64_decode_ignores_surrounding_whitespace() -> None:
    """Whitespace and newlines within a Base64 payload are ignored on decode."""

    payload = base64.b64encode(b"payload").decode("ascii")
    ok, content, _metadata = _run(f"  {payload[:2]}\n{payload[2:]}  ", operation="decode")

    assert ok is True
    assert content == "payload"


def test_base64_rejects_invalid_base64() -> None:
    """Non-Base64 input returns a structured failure, not a crash."""

    ok, content, _metadata = _run("not*valid*base64", operation="decode")

    assert ok is False
    assert "not valid base64" in content


def test_base64_rejects_non_utf8_payload() -> None:
    """Base64 that decodes to non-UTF-8 bytes is reported as a failure."""

    payload = base64.b64encode(b"\xff\xfe\xfd").decode("ascii")
    ok, content, _metadata = _run(payload, operation="decode")

    assert ok is False
    assert "utf-8" in content


def test_base64_rejects_unsupported_operation() -> None:
    """An unsupported operation returns a structured failure."""

    ok, content, _metadata = _run("hello", operation="transcode")

    assert ok is False
    assert "unsupported operation" in content


def test_base64_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content
