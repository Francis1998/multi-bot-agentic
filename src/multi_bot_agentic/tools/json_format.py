"""JSON validation and canonicalization tool.

Agent runs frequently pass JSON between steps (tool outputs, API payloads,
model-emitted structures). A malformed or inconsistently ordered document is a
common source of downstream failures. This tool validates a JSON document and
re-serialises it into a canonical, human-readable form (2-space indent, sorted
keys) without ever executing code. Invalid input returns a structured failure
with the parser's message rather than raising, matching the calculator tool's
contract.
"""

from __future__ import annotations

import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class JsonFormatTool:
    """Validate and canonicalize a JSON document."""

    name = "json_format"
    description = "Validates a JSON document and returns it canonicalized (sorted keys, indented)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate and canonicalize the JSON document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the JSON
                document to validate.

        Returns:
            Tool result with the canonicalized document, or ``ok=False`` and an
            explanation when the document is empty, too long, or invalid JSON.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="document is empty",
                metadata={},
            )
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        try:
            parsed = json.loads(document)
        except (json.JSONDecodeError, ValueError) as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid JSON: {error}",
                metadata={"chars": len(document)},
            )

        canonical = json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=canonical,
            metadata={"top_level_type": type(parsed).__name__},
        )
