"""Deterministic LLM provider for tests and demos."""

from __future__ import annotations

import json

from multi_bot_agentic.models import ModelOutput, ModelRequest
from multi_bot_agentic.structured_output import CORRECTION_SOURCE, OutputSchema, example_instance


class FakeLLMAdapter:
    """Fake provider that emits predictable outputs consumed by the runner."""

    provider_name = "fake"

    def __init__(self, tool_name: str = "checklist") -> None:
        """Initialize the adapter.

        Args:
            tool_name: Tool requested on the first turn (``TOOL:<tool_name>:<goal>``).
                Set ``MULTIBOT_FAKE_TOOL`` to demo another tool, such as an MCP tool.
        """

        self.tool_name = tool_name

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Return deterministic model output.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Model output containing either a tool request or final answer. After a human
            rejected the tool call, it re-plans by finishing without the tool. With an output
            schema, its first final answer is still plain text (like a model that ignores the
            format), so every fake run shows one correction round: after the validation errors it
            answers with a JSON document built from the schema, the goal, and the latest tool result.
        """

        latest = request.observations[-1] if request.observations else None
        if latest is not None and latest.source == CORRECTION_SOURCE and request.output_schema is not None:
            tool_results = [item for item in request.observations if item.source.startswith("tool:")]
            lines = tool_results[-1].content.splitlines() if tool_results else []
            document = example_instance(
                OutputSchema.from_value(request.output_schema),
                text=request.goal[:120],
                items=[line.strip().removeprefix("- ").removeprefix("* ") for line in lines],
            )
            return ModelOutput(
                provider=self.provider_name,
                text=f"DONE: {json.dumps(document, ensure_ascii=False)}",
                raw={"timeout_seconds": timeout_seconds, "mode": "deterministic-corrected-output"},
            )
        if latest is not None and latest.source.startswith("approval:"):
            tool = latest.source.removeprefix("approval:")
            reason = str(latest.metadata.get("reason") or "no reason given")
            return ModelOutput(
                provider=self.provider_name,
                text=f"DONE: re-planned without {tool} after a human rejected it ({reason})",
                raw={"timeout_seconds": timeout_seconds, "mode": "deterministic-replan-after-rejection"},
            )
        tool_results = [observation for observation in request.observations if observation.source.startswith("tool:")]
        if not tool_results:
            mode = "deterministic-checklist-request" if self.tool_name == "checklist" else "deterministic-tool-request"
            return ModelOutput(
                provider=self.provider_name,
                text=f"TOOL:{self.tool_name}:{request.goal[:120]}",
                raw={"timeout_seconds": timeout_seconds, "mode": mode},
            )
        return ModelOutput(
            provider=self.provider_name,
            text=f"DONE: synthesized plan from {len(request.observations)} observations",
            raw={"timeout_seconds": timeout_seconds, "mode": "deterministic-final"},
        )
