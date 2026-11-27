"""Base provider interface for LLM adapters."""

from __future__ import annotations

import json
from typing import Any, Protocol

from multi_bot_agentic.models import ModelOutput, ModelRequest, ToolSpec


class LLMAdapter(Protocol):
    """Protocol implemented by all LLM providers."""

    provider_name: str

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Return normalized model output.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Normalized model output.
        """


def render_tool_catalog(tools: tuple[ToolSpec, ...]) -> str:
    """Render advertised tools as a prompt section.

    Args:
        tools: Tool catalog from ``ModelRequest.tools``.

    Returns:
        A section starting with a blank line, or an empty string when no tools
        are advertised so existing prompts stay byte-for-byte unchanged.
    """

    if not tools:
        return ""
    lines = [
        "",
        "",
        "Available tools (request one with TOOL:<name>:<JSON object of arguments, or plain text "
        "for a single-argument tool>):",
    ]
    for spec in tools:
        line = f"- {spec.name}: {spec.description}"
        signature = spec.signature()
        if signature:
            line += f" Arguments: {signature}."
        lines.append(line)
    return "\n".join(lines)


def render_output_contract(schema: dict[str, Any] | bool | None) -> str:
    """Render a run's output schema as a prompt section.

    Args:
        schema: ``ModelRequest.output_schema``.

    Returns:
        A section starting with a blank line that asks for a JSON final answer and holds the
        compact schema, or an empty string without a schema so existing prompts stay unchanged.
    """

    if schema is None:
        return ""
    compact = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (
        "\n\nFinal answer contract: when finished, reply DONE: followed by only a JSON document "
        "(or exactly one ```json fenced block) that validates against this JSON Schema:\n" + compact
    )
