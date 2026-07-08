"""Tests for the cryptographic hashing tool."""

from __future__ import annotations

import hashlib

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.hashing import HashTool


def _run(text: str, algorithm: str | None = None) -> tuple[bool, str, dict[str, object]]:
    """Execute the hash tool for a document.

    Args:
        text: Document text to hash.
        algorithm: Optional digest algorithm to request.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text}
    if algorithm is not None:
        arguments["algorithm"] = algorithm
    result = HashTool().execute(ToolInvocation(tool_name="hash", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_hash_defaults_to_sha256() -> None:
    """Without an algorithm argument the tool returns a sha256 hex digest."""

    ok, content, metadata = _run("hello world")

    assert ok is True
    assert content == hashlib.sha256(b"hello world").hexdigest()
    assert metadata["algorithm"] == "sha256"
    assert metadata["bytes"] == len(b"hello world")


def test_hash_honors_requested_algorithm() -> None:
    """A supported algorithm argument selects that digest (case-insensitive)."""

    ok, content, metadata = _run("hello world", algorithm="SHA1")

    assert ok is True
    assert content == hashlib.sha1(b"hello world").hexdigest()
    assert metadata["algorithm"] == "sha1"


def test_hash_rejects_unsupported_algorithm() -> None:
    """An unsupported algorithm returns a structured failure, not a crash."""

    ok, content, _metadata = _run("hello", algorithm="crc32")

    assert ok is False
    assert "unsupported algorithm" in content


def test_hash_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content


def test_hash_is_deterministic_for_unicode() -> None:
    """The digest hashes the UTF-8 encoding and is stable across calls."""

    first_ok, first, _first_meta = _run("café")
    second_ok, second, _second_meta = _run("café")

    assert first_ok is True and second_ok is True
    assert first == second == hashlib.sha256("café".encode()).hexdigest()
