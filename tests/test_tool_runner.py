"""Tests for RateLimitedToolRunner."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from multi_bot_agentic.models import ToolInvocation, ToolResult
from multi_bot_agentic.tool_runner import RateLimitedToolRunner, RateLimitExceededError


@dataclass
class _FakeTool:
    """Minimal ToolAdapter stand-in."""

    name: str = "echo"
    description: str = "echo"
    calls: int = 0

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Execute fake tool."""

        self.calls += 1
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=str(invocation.arguments),
            metadata={},
        )


class _Clock:
    """Controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_under_limit() -> None:
    """Calls under the budget succeed."""

    tool = _FakeTool()
    runner = RateLimitedToolRunner({"echo": tool}, max_calls=3, window_seconds=10.0)
    for index in range(3):
        result = runner.execute(ToolInvocation(tool_name="echo", arguments={"i": index}))
        assert result.ok
    assert tool.calls == 3


def test_blocks_over_limit() -> None:
    """Fourth call in the same window raises RateLimitExceededError."""

    clock = _Clock()
    tool = _FakeTool()
    runner = RateLimitedToolRunner({"echo": tool}, max_calls=2, window_seconds=10.0, clock=clock)
    runner.execute(ToolInvocation(tool_name="echo", arguments={"v": "a"}))
    runner.execute(ToolInvocation(tool_name="echo", arguments={"v": "b"}))
    with pytest.raises(RateLimitExceededError) as exc:
        runner.execute(ToolInvocation(tool_name="echo", arguments={"v": "c"}))
    assert exc.value.details.tool_name == "echo"
    assert runner.remaining("echo") == 0


def test_window_expiry_frees_budget() -> None:
    """Advancing the clock beyond the window restores budget."""

    clock = _Clock()
    tool = _FakeTool()
    runner = RateLimitedToolRunner({"echo": tool}, max_calls=1, window_seconds=5.0, clock=clock)
    runner.execute(ToolInvocation(tool_name="echo", arguments={"v": "a"}))
    clock.now = 5.1
    result = runner.execute(ToolInvocation(tool_name="echo", arguments={"v": "b"}))
    assert result.ok
    assert tool.calls == 2


def test_unknown_tool_raises() -> None:
    """Unknown tool name raises KeyError."""

    runner = RateLimitedToolRunner({}, max_calls=1, window_seconds=1.0)
    with pytest.raises(KeyError):
        runner.execute(ToolInvocation(tool_name="missing", arguments={}))


def test_invalid_config_raises() -> None:
    """Invalid constructor args raise ValueError."""

    with pytest.raises(ValueError):
        RateLimitedToolRunner({}, max_calls=0)
    with pytest.raises(ValueError):
        RateLimitedToolRunner({}, window_seconds=0)
