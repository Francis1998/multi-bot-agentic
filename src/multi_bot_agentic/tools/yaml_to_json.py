"""YAML → JSON converter for agent handoffs.

Agents often receive configuration as YAML and need a portable JSON payload for
the next step. Full YAML includes anchors, tags, and constructors that are
unsafe or unnecessary for model handoffs. This tool reuses the same stdlib-only
safe YAML subset as ``yaml_format`` (no PyYAML dependency) and emits canonical
JSON. It never executes code, never evaluates YAML tags/constructors, and never
makes a network request — matching the ``toml_json``, ``yaml_format``, and
``json_format`` contracts for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.
"""

from __future__ import annotations

import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult
from multi_bot_agentic.tools.yaml_format import _YamlSubsetError, _YamlSubsetParser

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_RESULT_CHARS: Final[int] = 20_000


class YamlToJsonTool:
    """Convert a safe YAML subset document to canonical JSON."""

    name = "yaml_to_json"
    description = (
        "Converts a constrained safe YAML subset to canonical JSON "
        "(sorted keys, 2-space indent); rejects tags/anchors/constructors."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse YAML subset text and emit canonical JSON.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the YAML
                document to convert.

        Returns:
            Tool result with pretty JSON, or ``ok=False`` and an explanation when
            the document is empty, too long, outside the safe subset, or the
            serialized result exceeds the size bound.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        try:
            parsed = _YamlSubsetParser(document).parse()
            content = json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        except _YamlSubsetError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid YAML: {error}",
                metadata={"chars": len(document)},
            )
        except (TypeError, ValueError) as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"result is not serializable JSON: {error}",
                metadata={"chars": len(document)},
            )

        if len(content) > _MAX_RESULT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"result exceeds max_chars={_MAX_RESULT_CHARS}",
                metadata={"chars": len(content)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={"top_level_type": type(parsed).__name__, "chars": len(content)},
        )
