"""Offline golden-path evaluation harness for Observe-Decide-Act runs.

Compares tool sequences, DONE answers, and structured outputs (``output_schema`` /
``expected_output``) against fixtures using Fake / scripted LLM adapters. Intentionally local and
deterministic — not a hosted LangSmith / CrewAI evaluation cloud.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.structured_output import (
    DEFAULT_OUTPUT_RETRIES,
    MAX_OUTPUT_RETRIES,
    OutputContract,
    OutputExtractionError,
    OutputSchema,
    extract_json,
    json_key,
)

OUTPUT_MATCHES = ("exact", "subset")


@dataclass(frozen=True)
class ExpectedOutput:
    """The JSON output a scenario expects.

    Attributes:
        value: Expected JSON value.
        match: ``exact`` (JSON equality: ``1`` equals ``1.0``, key order is ignored) or ``subset``
            (every expected object key must be present with a matching value, arrays must have the
            same length and match item by item, other values must be equal).
    """

    value: Any
    match: str = "exact"


@dataclass(frozen=True)
class EvalScenario:
    """One golden-path evaluation scenario.

    Attributes:
        scenario_id: Stable fixture identifier.
        goal: User goal passed to the runner.
        scripted_responses: Ordered Fake-LLM outputs (`TOOL:` / `DONE:`).
        expected_tools: Every tool the run is expected to call, in order; any other call fails the scenario.
        expected_answer_contains: Optional substring that must appear in DONE answer.
        expected_answer: Optional exact DONE answer.
        max_steps: Step budget for the scenario.
        output_schema: Optional output schema; the run must end with an output that validates.
        output_retries: Correction rounds of the run when ``output_schema`` is set.
        expected_output: Optional expected JSON output (read from the answer when there is no schema).
    """

    scenario_id: str
    goal: str
    scripted_responses: tuple[str, ...]
    expected_tools: tuple[str, ...] = ()
    expected_answer_contains: str | None = None
    expected_answer: str | None = None
    max_steps: int = 6
    output_schema: OutputSchema | None = None
    output_retries: int = DEFAULT_OUTPUT_RETRIES
    expected_output: ExpectedOutput | None = None


@dataclass(frozen=True)
class ScenarioScore:
    """Scores for one scenario.

    ``details`` holds the run's final ``state``, its ``steps``, and the ``run_id`` that
    was scored in ``<event_log_dir>/<scenario_id>.sqlite``.
    """

    scenario_id: str
    tool_sequence_score: float
    answer_score: float
    passed: bool
    actual_tools: tuple[str, ...]
    actual_answer: str
    details: dict[str, Any]
    output_score: float = 1.0
    actual_output: Any = None


@dataclass(frozen=True)
class HarnessReport:
    """Aggregate evaluation report."""

    scenarios: tuple[ScenarioScore, ...]
    pass_rate: float
    mean_tool_sequence_score: float
    mean_answer_score: float
    mean_output_score: float = 1.0


class ScriptedLLMAdapter:
    """LLM adapter that returns fixture-scripted responses in order.

    Compatible with GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro
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

    Uses the longest common prefix length divided by the length of the longer sequence, so
    missing calls and calls beyond ``expected`` both lower the score. Only a run that called
    exactly ``expected``, in order, scores ``1.0``; two empty sequences also score ``1.0``.

    Args:
        actual: Tools invoked during the run.
        expected: Expected tool names in order.

    Returns:
        Sequence score.
    """

    longest = max(len(actual), len(expected))
    if longest == 0:
        return 1.0
    matched = 0
    for left, right in zip(actual, expected, strict=False):
        if left != right:
            break
        matched += 1
    return matched / longest


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


def json_subset(expected: Any, actual: Any) -> bool:
    """Return whether ``actual`` contains ``expected`` (see :class:`ExpectedOutput`)."""

    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and json_subset(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(json_subset(item, other) for item, other in zip(expected, actual, strict=True))
        )
    return bool(json_key(expected) == json_key(actual))


def score_output(
    *,
    has_schema: bool,
    output: Any,
    output_found: bool,
    expected: ExpectedOutput | None,
) -> float:
    """Score a run's structured output.

    Args:
        has_schema: Whether the scenario set ``output_schema``.
        output: The run's validated output, or the JSON read from its answer.
        output_found: Whether there is such an output.
        expected: Expected output, if any.

    Returns:
        ``1.0`` when nothing is asserted, or when the output exists (it validated, with a schema)
        and matches ``expected``; otherwise ``0.0``.
    """

    if not has_schema and expected is None:
        return 1.0
    if not output_found:
        return 0.0
    if expected is None:
        return 1.0
    if expected.match == "subset":
        return 1.0 if json_subset(expected.value, output) else 0.0
    return 1.0 if json_key(expected.value) == json_key(output) else 0.0


def load_scenario(path: Path) -> EvalScenario:
    """Load one scenario fixture from JSON.

    Args:
        path: Fixture file path (``.json``).

    Returns:
        Parsed scenario.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_schema = payload.get("output_schema")
    schema: OutputSchema | None = None
    if isinstance(raw_schema, str):
        schema = OutputSchema.load(path.parent / raw_schema)
    elif raw_schema is not None:
        schema = OutputSchema.from_value(raw_schema, source=f"{path.name}#output_schema")
    expected: ExpectedOutput | None = None
    if "expected_output" in payload:
        match = payload.get("expected_output_match", "exact")
        if match not in OUTPUT_MATCHES:
            raise ValueError(f"{path}: expected_output_match must be one of {', '.join(OUTPUT_MATCHES)}, got {match!r}")
        expected = ExpectedOutput(value=payload["expected_output"], match=match)
    retries = payload.get("output_retries", DEFAULT_OUTPUT_RETRIES)
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= MAX_OUTPUT_RETRIES:
        raise ValueError(f"{path}: output_retries must be an integer from 0 to {MAX_OUTPUT_RETRIES}, got {retries!r}")
    return EvalScenario(
        scenario_id=str(payload["scenario_id"]),
        goal=str(payload["goal"]),
        scripted_responses=tuple(str(item) for item in payload.get("scripted_responses", [])),
        expected_tools=tuple(str(item) for item in payload.get("expected_tools", [])),
        expected_answer_contains=payload.get("expected_answer_contains"),
        expected_answer=payload.get("expected_answer"),
        max_steps=int(payload.get("max_steps", 6)),
        output_schema=schema,
        output_retries=retries,
        expected_output=expected,
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
            event_log_dir: Directory for per-scenario sqlite logs. Every execution is logged
                as a new run, so earlier evaluations in the same directory never affect scores.

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
        mean_output = sum(item.output_score for item in scores) / len(scores)
        return HarnessReport(
            scenarios=tuple(scores),
            pass_rate=pass_rate,
            mean_tool_sequence_score=mean_tools,
            mean_answer_score=mean_answer,
            mean_output_score=mean_output,
        )

    def _run_one(self, scenario: EvalScenario, *, root: Path, event_log_dir: Path) -> ScenarioScore:
        """Run a single scenario under a fresh run id and score only that run's events."""

        provider: FakeLLMAdapter | ScriptedLLMAdapter
        if not scenario.scripted_responses:
            provider = FakeLLMAdapter()
        else:
            provider = ScriptedLLMAdapter(scenario.scripted_responses)
        log_path = event_log_dir / f"{scenario.scenario_id}.sqlite"
        # The log may already hold earlier evaluations of this scenario. Reusing their run id
        # would append to them, and scoring would read their tool calls first.
        run_id = f"{scenario.scenario_id}-{uuid4().hex[:12]}"
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
            contract = None
            if scenario.output_schema is not None:
                contract = OutputContract(schema=scenario.output_schema, retries=scenario.output_retries)
            result = runner.run(scenario.goal, run_id=run_id, output_contract=contract)
            events = event_log.list_events(result.run_id)
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
        output, found = _actual_output(scenario, result.output, result.answer)
        output_score = score_output(
            has_schema=scenario.output_schema is not None,
            output=output,
            output_found=found,
            expected=scenario.expected_output,
        )
        passed = tool_score >= 1.0 and answer_score >= 1.0 and output_score >= 1.0 and result.state.value == "succeeded"
        details: dict[str, Any] = {"state": result.state.value, "steps": result.steps, "run_id": result.run_id}
        if result.output is not None:
            details["output_attempts"] = result.output.attempt
        if result.output_errors:
            details["output_errors"] = list(result.output_errors)
        return ScenarioScore(
            scenario_id=scenario.scenario_id,
            tool_sequence_score=tool_score,
            answer_score=answer_score,
            passed=passed,
            actual_tools=actual_tools,
            actual_answer=result.answer,
            details=details,
            output_score=output_score,
            actual_output=output,
        )


def _actual_output(scenario: EvalScenario, validated: Any, answer: str) -> tuple[Any, bool]:
    """Return the output to score and whether there is one.

    With a schema it is the run's validated output; without one, ``expected_output`` is compared
    with the JSON read from the answer by the same rules (:func:`extract_json`).
    """

    if scenario.output_schema is not None:
        return (validated.value, True) if validated is not None else (None, False)
    if scenario.expected_output is None:
        return None, False
    try:
        value, _ = extract_json(answer)
    except OutputExtractionError:
        return None, False
    return value, True


def default_fixture_dir() -> Path:
    """Return the packaged fixture directory.

    Returns:
        Path to ``eval/fixtures``.
    """

    return Path(__file__).resolve().parent / "fixtures"
