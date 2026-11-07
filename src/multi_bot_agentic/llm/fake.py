"""Deterministic LLM provider for tests and demos."""

from __future__ import annotations

from multi_bot_agentic.models import ModelOutput, ModelRequest


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
            Model output containing either a tool request or final answer.
        """

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
