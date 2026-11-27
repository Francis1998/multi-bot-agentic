"""Provider usage parsing, run usage totals, and run-level usage limits.

Every model call the runner makes is recorded as an ``llm_usage`` event (provider, model, bot,
normalized :class:`~multi_bot_agentic.models.Usage`, cost). A run's totals are the sum of its
``llm_usage`` events, so ``resume`` continues them from the log, and a fork, whose inherited events
include the source's ``llm_usage`` events up to its fork point, starts from the totals at that point.

:class:`UsageLimits` bounds a run's requests, tokens, and cost. Limits are checked before every
model call against the running totals and after it against the actual usage; a breach stops the
run in the resumable ``usage_limit_exceeded`` state. A limit the totals cannot measure (a call
reported no tokens, or its model is unpriced) counts as breached, so a limit never silently stops
working.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any, Final

from multi_bot_agentic.event_log import EventRecord
from multi_bot_agentic.models import TOKEN_FIELDS, EventType, ModelRequest, Usage

# The offline providers report about four characters per token plus a fixed prompt overhead.
FAKE_CHARS_PER_TOKEN: Final[int] = 4
FAKE_PROMPT_OVERHEAD_TOKENS: Final[int] = 40
BEFORE_CALL: Final[str] = "before_call"
AFTER_CALL: Final[str] = "after_call"
# Limit name -> the running total it caps.
LIMIT_COUNTERS: Final[Mapping[str, str]] = {
    "max_requests": "requests",
    "max_input_tokens": "input_tokens",
    "max_output_tokens": "output_tokens",
    "max_total_tokens": "total_tokens",
    "max_cost_usd": "cost_usd",
}


def _count(value: Any) -> int | None:
    """Return ``value`` when it is a non-negative integer, else ``None``."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _detail(payload: Mapping[str, Any], section: str, key: str) -> Any:
    """Return ``payload[section][key]`` when ``section`` is an object."""

    nested = payload.get(section)
    return nested.get(key) if isinstance(nested, Mapping) else None


def _total(input_tokens: int | None, output_tokens: int | None, reported: int | None) -> int | None:
    """Return the reported total, else the sum of input and output when both are known."""

    if reported is not None:
        return reported
    if input_tokens is not None and output_tokens is not None:
        return input_tokens + output_tokens
    return None


def parse_openai_usage(payload: Any) -> Usage | None:
    """Parse an OpenAI-compatible ``usage`` object (OpenAI and Kimi adapters).

    Chat Completions reports ``prompt_tokens`` / ``completion_tokens`` with
    ``prompt_tokens_details.cached_tokens`` and ``completion_tokens_details.reasoning_tokens``; the
    Responses API reports ``input_tokens`` / ``output_tokens`` with ``input_tokens_details`` and
    ``output_tokens_details``. Both include cached tokens in the input and reasoning tokens in the
    output, matching :class:`Usage`.

    Args:
        payload: The response's ``usage`` value.

    Returns:
        Normalized usage, or ``None`` when the response reported no token counts.
    """

    if not isinstance(payload, Mapping):
        return None
    if "input_tokens" in payload or "output_tokens" in payload:
        input_tokens = _count(payload.get("input_tokens"))
        output_tokens = _count(payload.get("output_tokens"))
        cached = _count(_detail(payload, "input_tokens_details", "cached_tokens"))
        reasoning = _count(_detail(payload, "output_tokens_details", "reasoning_tokens"))
    else:
        input_tokens = _count(payload.get("prompt_tokens"))
        output_tokens = _count(payload.get("completion_tokens"))
        cached = _count(_detail(payload, "prompt_tokens_details", "cached_tokens"))
        reasoning = _count(_detail(payload, "completion_tokens_details", "reasoning_tokens"))
    total = _total(input_tokens, output_tokens, _count(payload.get("total_tokens")))
    if input_tokens is None and output_tokens is None and total is None:
        return None
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached,
        reasoning_tokens=reasoning,
        total_tokens=total,
    )


def parse_gemini_usage(payload: Any) -> Usage | None:
    """Parse a Gemini ``usageMetadata`` object.

    ``candidatesTokenCount`` excludes thinking tokens, so output is ``candidatesTokenCount +
    thoughtsTokenCount``; input is ``promptTokenCount`` (cached content included) plus
    ``toolUsePromptTokenCount``. The API omits zero counts (proto3 JSON), so a count missing from
    a present ``usageMetadata`` is ``0``.

    Args:
        payload: The response's ``usageMetadata`` value.

    Returns:
        Normalized usage, or ``None`` when the response reported no token counts.
    """

    if not isinstance(payload, Mapping):
        return None
    keys = (
        "promptTokenCount",
        "toolUsePromptTokenCount",
        "candidatesTokenCount",
        "thoughtsTokenCount",
        "cachedContentTokenCount",
        "totalTokenCount",
    )
    counts = {key: _count(payload.get(key)) for key in keys}
    if all(value is None for value in counts.values()):
        return None
    input_tokens = (counts["promptTokenCount"] or 0) + (counts["toolUsePromptTokenCount"] or 0)
    thoughts = counts["thoughtsTokenCount"] or 0
    output_tokens = (counts["candidatesTokenCount"] or 0) + thoughts
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=counts["cachedContentTokenCount"] or 0,
        reasoning_tokens=thoughts,
        total_tokens=_total(input_tokens, output_tokens, counts["totalTokenCount"]),
    )


def parse_anthropic_usage(payload: Any) -> Usage | None:
    """Parse an Anthropic-style ``usage`` object (Claude Code ``--output-format json``).

    Its ``input_tokens`` excludes cache reads and writes, so ``cache_read_input_tokens`` and
    ``cache_creation_input_tokens`` are added back; cache reads are the cached input tokens.
    Reasoning tokens are not reported separately and stay unknown.

    Args:
        payload: The result's ``usage`` value.

    Returns:
        Normalized usage, or ``None`` when no token counts were reported.
    """

    if not isinstance(payload, Mapping):
        return None
    base = _count(payload.get("input_tokens"))
    output_tokens = _count(payload.get("output_tokens"))
    if base is None and output_tokens is None:
        return None
    reads = _count(payload.get("cache_read_input_tokens")) or 0
    writes = _count(payload.get("cache_creation_input_tokens")) or 0
    input_tokens = None if base is None else base + reads + writes
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=None if base is None else reads,
        total_tokens=_total(input_tokens, output_tokens, None),
    )


def estimate_usage(request: ModelRequest, text: str) -> Usage:
    """Return the deterministic usage the offline providers (fake, scripted) report for one call.

    About four characters per token of goal, observations, and tool catalog, plus a fixed prompt
    overhead; the output is about four characters per token of the reply.

    Args:
        request: The model request.
        text: The reply text.

    Returns:
        Deterministic usage with no cached or reasoning tokens.
    """

    prompt_chars = len(request.goal)
    prompt_chars += sum(len(item.source) + len(item.content) for item in request.observations)
    prompt_chars += sum(len(spec.name) + len(spec.description) for spec in request.tools)
    input_tokens = FAKE_PROMPT_OVERHEAD_TOKENS + math.ceil(prompt_chars / FAKE_CHARS_PER_TOKEN)
    output_tokens = max(1, math.ceil(len(text) / FAKE_CHARS_PER_TOKEN))
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=0,
        reasoning_tokens=0,
        total_tokens=input_tokens + output_tokens,
    )


def _plus(left: int | None, right: int | None) -> int | None:
    """Add two optional counts; unknown plus known is the known one."""

    if right is None:
        return left
    return right if left is None else left + right


def _plus_usd(left: float | None, right: float | None) -> float | None:
    """Add two optional USD amounts, rounded to 1e-10."""

    if right is None:
        return left
    return right if left is None else round(left + right, 10)


@dataclass(frozen=True)
class UsageTotals:
    """Usage summed over model calls.

    A token counter (or ``cost_usd``) is ``None`` until a call reports it; it then sums the calls
    that did. ``unmeasured_requests`` counts calls that reported no input or output tokens and
    ``unpriced_requests`` calls without a cost, so a partial total is never mistaken for a full one.
    """

    requests: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    unmeasured_requests: int = 0
    unpriced_requests: int = 0

    def add(self, usage: Usage | None, cost_usd: float | None) -> UsageTotals:
        """Return the totals with one more model call added.

        Args:
            usage: Usage the call reported, or ``None`` when it reported none.
            cost_usd: Cost of the call, or ``None`` when it is unpriced.
        """

        call = usage or Usage()
        total = _total(call.input_tokens, call.output_tokens, call.total_tokens)
        return UsageTotals(
            requests=self.requests + call.requests,
            input_tokens=_plus(self.input_tokens, call.input_tokens),
            output_tokens=_plus(self.output_tokens, call.output_tokens),
            cached_input_tokens=_plus(self.cached_input_tokens, call.cached_input_tokens),
            reasoning_tokens=_plus(self.reasoning_tokens, call.reasoning_tokens),
            total_tokens=_plus(self.total_tokens, total),
            cost_usd=_plus_usd(self.cost_usd, cost_usd),
            unmeasured_requests=self.unmeasured_requests + (0 if call.measured else call.requests),
            unpriced_requests=self.unpriced_requests + (call.requests if cost_usd is None else 0),
        )

    def add_record(self, payload: Mapping[str, Any]) -> UsageTotals:
        """Return the totals with the call an ``llm_usage`` event payload records added."""

        cost = payload.get("cost")
        usd = cost.get("usd") if isinstance(cost, Mapping) else None
        valid_usd = float(usd) if isinstance(usd, (int, float)) and not isinstance(usd, bool) else None
        return self.add(Usage.from_dict(payload.get("usage")), valid_usd)

    def merge(self, other: UsageTotals) -> UsageTotals:
        """Return the sum of two totals."""

        return UsageTotals(
            requests=self.requests + other.requests,
            **{name: _plus(getattr(self, name), getattr(other, name)) for name in TOKEN_FIELDS},
            cost_usd=_plus_usd(self.cost_usd, other.cost_usd),
            unmeasured_requests=self.unmeasured_requests + other.unmeasured_requests,
            unpriced_requests=self.unpriced_requests + other.unpriced_requests,
        )

    def value(self, counter: str) -> int | float | None:
        """Return the running total a limit caps (``requests``, a token counter, or ``cost_usd``)."""

        value: int | float | None = getattr(self, counter)
        return value

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {item.name: getattr(self, item.name) for item in fields(self)}

    @classmethod
    def from_events(cls, events: Iterable[EventRecord]) -> UsageTotals:
        """Sum the ``llm_usage`` events among ``events``."""

        totals = cls()
        for event in events:
            if event.event_type == EventType.LLM_USAGE.value:
                totals = totals.add_record(event.payload)
        return totals


def format_number(value: int | float | None) -> str:
    """Format a counter or USD amount for messages (``unknown`` for ``None``)."""

    if value is None:
        return "unknown"
    if isinstance(value, int):
        return str(value)
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


@dataclass(frozen=True)
class LimitBreach:
    """A usage limit that stopped a run.

    Attributes:
        limit: Limit name (``max_total_tokens``, ...).
        counter: Running total the limit caps.
        value: The total when the run stopped; ``None`` when it cannot be measured.
        cap: The limit.
        phase: ``before_call`` (the next call would exceed it) or ``after_call`` (a call exceeded it).
        unknown_calls: Calls whose tokens or cost are unknown, when ``value`` is ``None``.
    """

    limit: str
    counter: str
    value: int | float | None
    cap: int | float
    phase: str
    unknown_calls: int = 0

    @property
    def message(self) -> str:
        """Return a one-line explanation."""

        cap = format_number(self.cap)
        if self.value is None:
            missing = "cost (unpriced model)" if self.counter == "cost_usd" else "token usage"
            return f"{self.limit}={cap} cannot be enforced: {self.unknown_calls} model call(s) reported no {missing}"
        value = format_number(self.value)
        if self.phase == BEFORE_CALL:
            return f"the next model call would exceed {self.limit}={cap} ({self.counter}={value})"
        return f"{self.counter}={value} exceeded {self.limit}={cap}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        payload: dict[str, Any] = {
            "limit": self.limit,
            "counter": self.counter,
            "value": self.value,
            "cap": self.cap,
            "phase": self.phase,
            "message": self.message,
        }
        if self.value is None:
            payload["unknown_calls"] = self.unknown_calls
        return payload


@dataclass(frozen=True)
class UsageLimits:
    """Run-level caps on model usage; ``None`` leaves a counter unlimited.

    Attributes:
        max_requests: Model calls.
        max_input_tokens: Input tokens (cached included).
        max_output_tokens: Output tokens (reasoning included).
        max_total_tokens: Total tokens.
        max_cost_usd: Cost in USD.
    """

    max_requests: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        """Reject negative or non-finite limits.

        Raises:
            ValueError: If a limit is negative or not finite.
        """

        for name in LIMIT_COUNTERS:
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be >= 0, got {value!r}")

    @property
    def active(self) -> dict[str, int | float]:
        """Return the limits that are set, by name."""

        return {name: getattr(self, name) for name in LIMIT_COUNTERS if getattr(self, name) is not None}

    def override(self, other: UsageLimits) -> UsageLimits:
        """Return these limits with every limit ``other`` sets replacing this one's."""

        merged = {**self.active, **other.active}
        return UsageLimits.from_dict(merged)

    def to_dict(self) -> dict[str, int | float]:
        """Return the limits that are set (JSON-serializable)."""

        return self.active

    @classmethod
    def from_dict(cls, payload: Any) -> UsageLimits:
        """Rebuild limits recorded by :meth:`to_dict`; unknown or malformed entries are ignored."""

        if not isinstance(payload, Mapping):
            return cls()
        values: dict[str, Any] = {}
        for name in LIMIT_COUNTERS:
            value = payload.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value) or value < 0:
                continue
            values[name] = float(value) if name == "max_cost_usd" else int(value)
        return cls(**values)

    def check(self, totals: UsageTotals, phase: str) -> LimitBreach | None:
        """Return the first limit the running totals breach, or ``None``.

        Before a call (``before_call``) a limit is breached when the total has reached it, since
        the call can only add to it (``max_requests``: the call would be one too many). After a
        call (``after_call``) it is breached when the total exceeds it.

        Args:
            totals: Running totals of the run.
            phase: ``before_call`` or ``after_call``.

        Returns:
            The breach, or ``None`` when every limit holds.
        """

        for name, counter in LIMIT_COUNTERS.items():
            cap = getattr(self, name)
            if cap is None:
                continue
            if counter != "requests":
                unknown = totals.unpriced_requests if counter == "cost_usd" else totals.unmeasured_requests
                if unknown:
                    return LimitBreach(name, counter, None, cap, phase, unknown_calls=unknown)
            value = totals.value(counter) or 0
            if value > cap or (phase == BEFORE_CALL and value >= cap):
                return LimitBreach(name, counter, value, cap, phase)
        return None


def usage_rows(events: Sequence[EventRecord], key: str) -> list[dict[str, Any]]:
    """Group ``llm_usage`` events by ``bot`` or by ``provider`` and ``model``, with totals per group."""

    groups: dict[tuple[Any, ...], UsageTotals] = {}
    for event in events:
        if event.event_type != EventType.LLM_USAGE.value:
            continue
        payload = event.payload
        group = (payload.get("bot"),) if key == "bot" else (payload.get("provider"), payload.get("model"))
        groups[group] = groups.get(group, UsageTotals()).add_record(payload)
    names = ("bot",) if key == "bot" else ("provider", "model")
    return [
        {**dict(zip(names, group, strict=True)), **totals.to_dict()}
        for group, totals in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0]))
    ]


def usage_summary(events: Sequence[EventRecord], *, inherited_through_seq: int = 0) -> dict[str, Any]:
    """Summarize one run's model usage for ``report`` and ``eval``.

    Args:
        events: The run's events.
        inherited_through_seq: Last sequence number a fork copied from its source run (``0`` for
            runs that are not forks). Those calls are reported as ``inherited``, not as the run's own.

    Returns:
        The run's own totals, plus ``by_bot`` and ``by_model`` rows, ``inherited`` totals and the
        ``running`` totals its limits count (forks only), and the usage-limit stops it recorded.
    """

    own = [event for event in events if event.seq > inherited_through_seq]
    inherited = [event for event in events if event.seq <= inherited_through_seq]
    own_totals = UsageTotals.from_events(own)
    summary: dict[str, Any] = {
        **own_totals.to_dict(),
        "by_bot": usage_rows(own, "bot"),
        "by_model": usage_rows(own, "model"),
    }
    inherited_totals = UsageTotals.from_events(inherited)
    if inherited_totals.requests:
        summary["inherited"] = inherited_totals.to_dict()
        summary["running"] = inherited_totals.merge(own_totals).to_dict()
    stops = [
        {key: event.payload.get(key) for key in ("limit", "value", "cap", "phase", "step")}
        for event in own
        if event.event_type == EventType.USAGE_LIMIT_EXCEEDED.value
    ]
    if stops:
        summary["limit_stops"] = stops
    return summary
