"""Tests for the deterministic ISO-8601 duration parsing tool."""

from __future__ import annotations

import json

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.duration_parse import DurationTool


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the duration tool for a duration string.

    Args:
        text: ISO-8601 duration text to parse.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = DurationTool().execute(ToolInvocation(tool_name="duration", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_duration_parses_hours_and_minutes() -> None:
    """A ``PT1H30M`` duration resolves to 5400 seconds."""

    ok, content, metadata = _run("PT1H30M")

    assert ok is True
    assert metadata["total_seconds"] == 5400
    assert metadata["hours"] == 1
    assert metadata["minutes"] == 30
    assert json.loads(content)["total_seconds"] == 5400


def test_duration_parses_days_and_time() -> None:
    """A ``P1DT2H`` duration resolves to 93600 seconds."""

    ok, _content, metadata = _run("P1DT2H")

    assert ok is True
    assert metadata["total_seconds"] == 93600
    assert metadata["days"] == 1
    assert metadata["hours"] == 2


def test_duration_parses_weeks() -> None:
    """A ``P2W`` duration resolves to two weeks of seconds."""

    ok, _content, metadata = _run("P2W")

    assert ok is True
    assert metadata["total_seconds"] == 1_209_600
    assert metadata["weeks"] == 2


def test_duration_parses_fractional_seconds() -> None:
    """A fractional smallest component is preserved as a float."""

    ok, _content, metadata = _run("PT0.5S")

    assert ok is True
    assert metadata["total_seconds"] == 0.5


def test_duration_parses_negative_sign() -> None:
    """A leading ``-`` negates the total and is reported as ``negative``."""

    ok, _content, metadata = _run("-PT1H")

    assert ok is True
    assert metadata["total_seconds"] == -3600
    assert metadata["negative"] is True


def test_duration_rejects_calendar_components() -> None:
    """Years and months are refused because they have no fixed second length.

    A month is 28-31 days and a year 365/366 days, so converting ``P1Y2M3D`` or
    ``P1M`` to seconds would silently produce an inexact result. The date-part
    ``Y``/``M`` designators must be refused while a time-part ``M`` (minutes)
    stays valid.
    """

    for text in ("P1Y2M3D", "P1M", "P1Y"):
        ok, content, _metadata = _run(text)
        assert ok is False
        assert "calendar" in content

    # A time-part M is minutes, not months, and must still parse.
    ok, _content, metadata = _run("PT15M")
    assert ok is True
    assert metadata["minutes"] == 15


def test_duration_rejects_empty_and_componentless() -> None:
    """A bare ``P``/``PT`` and non-duration text return structured failures."""

    ok_empty, content_empty, _ = _run("   ")
    assert ok_empty is False
    assert "empty" in content_empty

    ok_bare, content_bare, _ = _run("PT")
    assert ok_bare is False
    assert "no components" in content_bare

    ok_bad, content_bad, _ = _run("1H")
    assert ok_bad is False
    assert "could not parse" in content_bad
