"""Tests for the deterministic namespaced UUID (version 5) tool."""

from __future__ import annotations

import uuid

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.uuid5 import Uuid5Tool


def _run(text: str, namespace: str | None = None) -> tuple[bool, str, dict[str, object]]:
    """Execute the uuid5 tool for a name and optional namespace.

    Args:
        text: Name to hash into a UUID.
        namespace: Optional namespace alias or custom UUID string.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text}
    if namespace is not None:
        arguments["namespace"] = namespace
    result = Uuid5Tool().execute(ToolInvocation(tool_name="uuid5", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_uuid5_matches_stdlib_for_dns_namespace() -> None:
    """The default (dns) namespace matches the standard library computation."""

    ok, content, metadata = _run("example.com")

    assert ok is True
    assert content == str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))
    assert metadata["version"] == 5


def test_uuid5_is_deterministic_across_calls() -> None:
    """The same name and namespace always yield the same UUID."""

    _ok1, first, _m1 = _run("agent-observation-42", namespace="url")
    _ok2, second, _m2 = _run("agent-observation-42", namespace="url")

    assert first == second == str(uuid.uuid5(uuid.NAMESPACE_URL, "agent-observation-42"))


def test_uuid5_accepts_custom_uuid_namespace() -> None:
    """A custom UUID string is accepted as the namespace."""

    custom = "12345678-1234-5678-1234-567812345678"
    ok, content, _metadata = _run("payload", namespace=custom)

    assert ok is True
    assert content == str(uuid.uuid5(uuid.UUID(custom), "payload"))


def test_uuid5_rejects_unusable_namespace() -> None:
    """A namespace that is neither a known alias nor a valid UUID fails."""

    ok, content, _metadata = _run("payload", namespace="not-a-namespace")

    assert ok is False
    assert "unusable namespace" in content


def test_uuid5_rejects_empty_name() -> None:
    """An empty name is reported as a structured failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content
