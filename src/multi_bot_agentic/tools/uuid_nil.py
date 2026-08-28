"""Nil / max UUID placeholder tool for agent pipelines.

CrewAI / LangGraph-style agent stacks often need a stable placeholder id before
a real identifier is assigned. Asking a model to emit the RFC 4122 nil UUID is
unreliable (wrong zero counts, missing dashes, invented variants). This tool
returns the nil UUID ``00000000-0000-0000-0000-000000000000`` by default, or the
max UUID when ``mode=max``. It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from multi_bot_agentic.models import ToolInvocation, ToolResult

_NIL_UUID: Final[str] = str(UUID(int=0))
_MAX_UUID: Final[str] = str(UUID(int=(1 << 128) - 1))
_DEFAULT_MODE: Final[str] = "nil"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"nil", "max"})


class UuidNilTool:
    """Return the RFC 4122 nil UUID or the all-ones max UUID."""

    name = "uuid_nil"
    description = (
        "Returns the RFC 4122 nil UUID (00000000-0000-0000-0000-000000000000) or max UUID when mode=max; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return a constant nil or max UUID string.

        Args:
            invocation: Tool invocation whose optional ``mode`` argument selects
                ``nil`` (default) or ``max``.

        Returns:
            Tool result whose ``content`` is the UUID string, or ``ok=False``
            when ``mode`` is unsupported.
        """

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        content = _NIL_UUID if mode == "nil" else _MAX_UUID
        metadata: dict[str, object] = {"mode": mode, "chars": len(content)}
        if mode == "nil":
            metadata["nil"] = True
        else:
            metadata["max"] = True
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata=metadata,
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
