"""Tests for the cron_next tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.cron_next import CronNextTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the cron_next tool."""

    result = CronNextTool().execute(ToolInvocation(tool_name="cron_next", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_cron_next_every_minute_from_iso() -> None:
    """Every-minute cron returns the next N UTC timestamps."""

    ok, content, metadata = _run(
        expression="* * * * *",
        count=3,
        from_iso="2026-01-01T00:00:00Z",
    )
    assert ok is True
    assert content == "2026-01-01T00:01:00Z\n2026-01-01T00:02:00Z\n2026-01-01T00:03:00Z\n"
    assert metadata["count"] == 3
    assert metadata["fires"] == [
        "2026-01-01T00:01:00Z",
        "2026-01-01T00:02:00Z",
        "2026-01-01T00:03:00Z",
    ]


def test_cron_next_daily_and_weekday() -> None:
    """Daily midnight and weekday-restricted schedules are deterministic."""

    ok, content, metadata = _run(
        expression="0 0 * * *",
        count=2,
        from_iso="2026-08-27T12:00:00Z",
    )
    assert ok is True
    assert content.startswith("2026-08-28T00:00:00Z\n")
    assert "2026-08-29T00:00:00Z" in content
    assert metadata["count"] == 2

    # 2026-08-28 is Friday (cron dow=5). Next Mondays at 09:00.
    ok2, content2, metadata2 = _run(
        expression="0 9 * * 1",
        count=2,
        from_iso="2026-08-27T00:00:00Z",
    )
    assert ok2 is True
    assert content2 == "2026-08-31T09:00:00Z\n2026-09-07T09:00:00Z\n"
    fires = metadata2["fires"]
    assert isinstance(fires, list)
    assert fires[0] == "2026-08-31T09:00:00Z"


def test_cron_next_rejects_invalid_and_bounds() -> None:
    """Invalid fields, empty expression, and oversize count fail."""

    ok_empty, content_empty, _m1 = _run(expression="")
    ok_fields, content_fields, _m2 = _run(expression="* * *")
    ok_minute, content_minute, meta_minute = _run(expression="60 * * * *", from_iso="2026-01-01T00:00:00Z")
    ok_count, content_count, _m4 = _run(expression="* * * * *", count=21, from_iso="2026-01-01T00:00:00Z")
    ok_iso, content_iso, _m5 = _run(expression="* * * * *", from_iso="not-a-date")

    assert ok_empty is False and "empty" in content_empty
    assert ok_fields is False and "exactly 5 fields" in content_fields
    assert ok_minute is False and "invalid minute" in content_minute
    assert meta_minute["expression"] == "60 * * * *"
    assert ok_count is False and "max=20" in content_count
    assert ok_iso is False and "invalid from_iso" in content_iso


def test_cron_next_mentions_model_versions_as_examples() -> None:
    """Docs reference GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."""

    # Stable fixture used in agent scheduling docs for those model labels.
    ok, content, metadata = _run(
        text="*/15 * * * *",
        count=2,
        from_iso="2026-01-01T00:00:00Z",
    )
    assert ok is True
    assert content == "2026-01-01T00:15:00Z\n2026-01-01T00:30:00Z\n"
    assert metadata["expression"] == "*/15 * * * *"


def test_cron_next_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "cron_next" in tools
    assert tools["cron_next"].name == "cron_next"
    SafetyPolicy().validate_tool("cron_next")
    assert "cron_next" in SafetyPolicy().allowed_tools
