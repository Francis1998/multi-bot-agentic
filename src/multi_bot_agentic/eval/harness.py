"""Offline golden-path evaluation harness for Observe-Decide-Act runs.

Compares tool sequences and DONE answers against fixtures using Fake / scripted
LLM adapters. Intentionally local and deterministic — not a hosted LangSmith /
CrewAI evaluation cloud.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy


@dataclass(frozen=True)
class EvalScenario:
    """One golden-path evaluation scenario.

    Attributes:
        scenario_id: Stable fixture identifier.
        goal: User goal passed to the runner.
        scripted_responses: Ordered Fake-LLM outputs (`TOOL:` / `DONE:`).
        expected_tools: Expected tool names in order.
        expected_answer_contains: Optional substring that must appear in DONE answer.
        expected_answer: Optional exact DONE answer.
        max_steps: Step budget for the scenario.
    """

    scenario_id: str
    goal: str
    scripted_responses: tuple[str, ...]
    expected_tools: tuple[str, ...] = ()
    expected_answer_contains: str | None = None
    expected_answer: str | None = None
    max_steps: int = 6


@dataclass(frozen=True)
class ScenarioScore:
    """Scores for one scenario."""

    scenario_id: str
    tool_sequence_score: float
    answer_score: float
    passed: bool
    actual_tools: tuple[str, ...]
    actual_answer: str
    details: dict[str, Any]


@dataclass(frozen=True)
class HarnessReport:
    """Aggregate evaluation report."""

    scenarios: tuple[ScenarioScore, ...]
    pass_rate: float
    mean_tool_sequence_score: float
    mean_answer_score: float


class ScriptedLLMAdapter:
    """LLM adapter that returns fixture-scripted responses in order.

    Compatible with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
    directive formats (`TOOL:` / `DONE:`) used by the decision engine.
    """

    provider_name = "fake"

    def __init__(self, responses: tuple[str, ...]) -> None:
        """Initialize with ordered scripted responses.

        Args:
            responses: Model output texts to emit sequentially.
        """

        if not responses:
            raise ValueError("responses must be non-empty")
        self._responses = responses
        self._index = 0

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Return the next scripted response.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Scripted model output.
        """

        del request
        if self._index >= len(self._responses):
            text = "DONE: scripted responses exhausted"
        else:
            text = self._responses[self._index]
            self._index += 1
        return ModelOutput(
            provider=self.provider_name,
            text=text,
            raw={"timeout_seconds": timeout_seconds, "scripted_index": self._index},
        )


def score_tool_sequence(actual: tuple[str, ...], expected: tuple[str, ...]) -> float:
    """Score tool-sequence fidelity in ``[0.0, 1.0]``.

    Uses longest common prefix length divided by ``max(len(expected), 1)``.
    When ``expected`` is empty, returns ``1.0`` if ``actual`` is also empty else ``0.0``.

    Args:
        actual: Tools invoked during the run.
        expected: Expected tool names in order.

    Returns:
        Sequence score.
    """

    if not expected:
        return 1.0 if not actual else 0.0
    matched = 0
    for left, right in zip(actual, expected, strict=False):
        if left != right:
            break
        matched += 1
    return matched / len(expected)


def score_answer(
    actual_answer: str,
    *,
    expected_answer: str | None = None,
    expected_answer_contains: str | None = None,
) -> float:
    """Score the DONE answer.

    Args:
        actual_answer: Final run answer.
        expected_answer: Optional exact match.
        expected_answer_contains: Optional required substring.

    Returns:
        ``1.0`` on match, otherwise ``0.0``. When neither expectation is set, ``1.0``.
    """

    if expected_answer is None and expected_answer_contains is None:
        return 1.0
    if expected_answer is not None and actual_answer.strip() != expected_answer.strip():
        return 0.0
    if expected_answer_contains is not None and expected_answer_contains not in actual_answer:
        return 0.0
    return 1.0


def load_scenario(path: Path) -> EvalScenario:
    """Load one scenario fixture from JSON.

    Args:
        path: Fixture file path (``.json``).

    Returns:
        Parsed scenario.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvalScenario(
        scenario_id=str(payload["scenario_id"]),
        goal=str(payload["goal"]),
        scripted_responses=tuple(str(item) for item in payload.get("scripted_responses", [])),
        expected_tools=tuple(str(item) for item in payload.get("expected_tools", [])),
        expected_answer_contains=payload.get("expected_answer_contains"),
        expected_answer=payload.get("expected_answer"),
        max_steps=int(payload.get("max_steps", 6)),
    )


def load_scenarios(directory: Path) -> tuple[EvalScenario, ...]:
    """Load all ``*.json`` scenarios from a directory.

    Args:
        directory: Fixture directory.

    Returns:
        Scenarios sorted by scenario_id.
    """

    files = sorted(directory.glob("*.json"))
    return tuple(load_scenario(path) for path in files)


class EvaluationHarness:
    """Run fixture scenarios against Fake/scripted LLM + allowlisted tools.

    Gap vs LangSmith / CrewAI evals: fully offline, fixture-driven, scores only
    tool order + DONE answer — no hosted traces, dataset UI, or LLM-as-judge.
    """

    def __init__(self, scenarios: tuple[EvalScenario, ...]) -> None:
        """Create a harness.

        Args:
            scenarios: Evaluation scenarios.

        Raises:
            ValueError: If scenarios is empty.
        """

        if not scenarios:
            raise ValueError("scenarios must be non-empty")
        self.scenarios = scenarios

    def run(self, root: Path, event_log_dir: Path) -> HarnessReport:
        """Execute all scenarios and return an aggregate report.

        Args:
            root: Workspace root for readonly tools.
            event_log_dir: Directory for per-scenario sqlite logs.

        Returns:
            Aggregate harness report.
        """

        event_log_dir.mkdir(parents=True, exist_ok=True)
        scores: list[ScenarioScore] = []
        for scenario in self.scenarios:
            scores.append(self._run_one(scenario, root=root, event_log_dir=event_log_dir))
        pass_rate = sum(1 for item in scores if item.passed) / len(scores)
        mean_tools = sum(item.tool_sequence_score for item in scores) / len(scores)
        mean_answer = sum(item.answer_score for item in scores) / len(scores)
        return HarnessReport(
            scenarios=tuple(scores),
            pass_rate=pass_rate,
            mean_tool_sequence_score=mean_tools,
            mean_answer_score=mean_answer,
        )

    def _run_one(self, scenario: EvalScenario, *, root: Path, event_log_dir: Path) -> ScenarioScore:
        """Run a single scenario."""

        provider: FakeLLMAdapter | ScriptedLLMAdapter
        if not scenario.scripted_responses:
            provider = FakeLLMAdapter()
        else:
            provider = ScriptedLLMAdapter(scenario.scripted_responses)
        log_path = event_log_dir / f"{scenario.scenario_id}.sqlite"
        event_log = SQLiteEventLog(log_path)
        try:
            tools = build_default_tools(root=root)
            allowed = frozenset(tools) | frozenset(scenario.expected_tools)
            runner = AgentRunner(
                provider=provider,
                event_log=event_log,
                tools=tools,
                safety_policy=SafetyPolicy(max_steps=scenario.max_steps, allowed_tools=allowed),
            )
            result = runner.run(scenario.goal, run_id=scenario.scenario_id)
            events = event_log.list_events(scenario.scenario_id)
        finally:
            event_log.close()

        actual_tools = tuple(
            str(event.payload.get("tool"))
            for event in events
            if event.event_type == EventType.ACTION_RESULT.value
            and event.payload.get("kind") == "tool"
            and event.payload.get("tool")
        )
        tool_score = score_tool_sequence(actual_tools, scenario.expected_tools)
        answer_score = score_answer(
            result.answer,
            expected_answer=scenario.expected_answer,
            expected_answer_contains=scenario.expected_answer_contains,
        )
        passed = tool_score >= 1.0 and answer_score >= 1.0 and result.state.value == "succeeded"
        return ScenarioScore(
            scenario_id=scenario.scenario_id,
            tool_sequence_score=tool_score,
            answer_score=answer_score,
            passed=passed,
            actual_tools=actual_tools,
            actual_answer=result.answer,
            details={"state": result.state.value, "steps": result.steps},
        )


def default_fixture_dir() -> Path:
    """Return the packaged fixture directory.

    Returns:
        Path to ``eval/fixtures``.
    """

    return Path(__file__).resolve().parent / "fixtures"
