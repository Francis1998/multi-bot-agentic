"""Base provider interface for LLM adapters."""

from __future__ import annotations

from typing import Protocol

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
