"""Tests for the deterministic ISO-8601 datetime normalization tool."""

from __future__ import annotations

import json

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.datetime_normalize import DateTimeTool


def _run(text: str, **arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the datetime tool for a timestamp and optional arguments.

    Args:
        text: Timestamp text to normalize.
        **arguments: Optional ``assume_utc`` override.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    payload: dict[str, object] = {"text": text, **arguments}
    result = DateTimeTool().execute(ToolInvocation(tool_name="datetime", arguments=payload))
    return result.ok, result.content, result.metadata


def test_datetime_normalizes_zulu_designator_to_utc() -> None:
    """A trailing ``Z`` timestamp normalizes to a canonical ``+00:00`` UTC value."""

    ok, content, metadata = _run("2026-07-14T13:04:33Z")

    assert ok is True
    assert metadata["utc"] == "2026-07-14T13:04:33+00:00"
    assert metadata["weekday"] == "Tuesday"
    assert metadata["assumed_utc"] is False
    assert json.loads(content)["epoch_seconds"] == metadata["epoch_seconds"]


def test_datetime_converts_offset_to_utc() -> None:
    """A timestamp with a non-zero offset is converted to the equivalent UTC time."""

    ok, _content, metadata = _run("2026-07-14T15:04:33+02:00")

    assert ok is True
    assert metadata["utc"] == "2026-07-14T13:04:33+00:00"


def test_datetime_epoch_is_correct() -> None:
    """The Unix epoch is computed from the UTC instant, independent of offset."""

    _ok_a, _c_a, meta_a = _run("2026-07-14T13:04:33Z")
    _ok_b, _c_b, meta_b = _run("2026-07-14T15:04:33+02:00")

    assert meta_a["epoch_seconds"] == meta_b["epoch_seconds"]


def test_datetime_rejects_naive_without_assume_utc() -> None:
    """A naive timestamp is ambiguous and must fail unless ``assume_utc`` is set."""

    ok, content, _metadata = _run("2026-07-14T13:04:33")

    assert ok is False
    assert "naive" in content


def test_datetime_accepts_naive_with_assume_utc() -> None:
    """With ``assume_utc`` a naive timestamp is interpreted as UTC and flagged."""

    ok, _content, metadata = _run("2026-07-14 13:04:33", assume_utc=True)

    assert ok is True
    assert metadata["utc"] == "2026-07-14T13:04:33+00:00"
    assert metadata["assumed_utc"] is True


def test_datetime_rejects_non_boolean_assume_utc() -> None:
    """A non-boolean ``assume_utc`` argument is a structured failure."""

    ok, content, _metadata = _run("2026-07-14T13:04:33", assume_utc="maybe")

    assert ok is False
    assert "assume_utc" in content


def test_datetime_rejects_unparseable_timestamp() -> None:
    """A value that is not ISO-8601 is reported as a failure, not a crash."""

    ok, content, _metadata = _run("14 July 2026, 1pm")

    assert ok is False
    assert "ISO-8601" in content


def test_datetime_rejects_empty_document() -> None:
    """An empty timestamp is reported as a failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content


def test_datetime_is_registered_and_allowlisted() -> None:
    """The tool is wired into the default registry and the safety allowlist."""

    from pathlib import Path

    from multi_bot_agentic.runner import build_default_tools
    from multi_bot_agentic.safety import SafetyPolicy

    tools = build_default_tools(root=Path.cwd())
    assert "datetime" in tools
    assert "datetime" in SafetyPolicy().allowed_tools
