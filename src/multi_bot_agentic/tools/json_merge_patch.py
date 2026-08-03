"""JSON Merge Patch (RFC 7396) tool for agent payload handoffs.

Agents often need to apply a partial JSON update onto a base document without
losing sibling keys. Asking a language model to merge objects invents fields
and drops nested maps. This tool applies RFC 7396 JSON Merge Patch using
stdlib :mod:`json` only. It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
"""

from __future__ import annotations

import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_DEPTH: Final[int] = 32


class JsonMergePatchTool:
    """Apply an RFC 7396 JSON Merge Patch onto a base document."""

    name = "json_merge_patch"
    description = "Applies RFC 7396 JSON Merge Patch (base+patch JSON) via stdlib json; max 20_000 chars."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Merge ``patch`` onto ``base`` using RFC 7396 semantics.

        Args:
            invocation: Tool invocation with ``base`` and ``patch`` JSON text
                arguments (or ``text`` containing ``base<<<PATCH>>>patch``).

        Returns:
            Tool result with canonical merged JSON, or ``ok=False`` when input
            is empty, oversized, malformed, or exceeds depth limits.
        """

        base_raw = str(invocation.arguments.get("base", "")).strip()
        patch_raw = str(invocation.arguments.get("patch", "")).strip()
        if not base_raw and not patch_raw:
            combined = str(invocation.arguments.get("text", ""))
            if "<<<PATCH>>>" in combined:
                base_raw, patch_raw = combined.split("<<<PATCH>>>", 1)
                base_raw = base_raw.strip()
                patch_raw = patch_raw.strip()

        if not base_raw:
            return self._fail("base JSON is empty", {})
        if not patch_raw:
            return self._fail("patch JSON is empty", {})
        if len(base_raw) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"base exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(base_raw)},
            )
        if len(patch_raw) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"patch exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(patch_raw)},
            )

        try:
            base_value = json.loads(base_raw)
        except json.JSONDecodeError as exc:
            return self._fail(f"base JSON parse error: {exc.msg}", {"pos": exc.pos})
        try:
            patch_value = json.loads(patch_raw)
        except json.JSONDecodeError as exc:
            return self._fail(f"patch JSON parse error: {exc.msg}", {"pos": exc.pos})

        try:
            merged = self._merge(base_value, patch_value, depth=0)
        except ValueError as exc:
            return self._fail(str(exc), {})

        content = json.dumps(merged, sort_keys=True, indent=2, ensure_ascii=False)
        content += "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "base_type": type(base_value).__name__,
                "patch_type": type(patch_value).__name__,
            },
        )

    @classmethod
    def _merge(cls, target: object, patch: object, depth: int) -> object:
        """Apply RFC 7396 merge semantics recursively."""

        if depth > _MAX_DEPTH:
            raise ValueError(f"merge exceeds max_depth={_MAX_DEPTH}")
        if not isinstance(patch, dict):
            return patch
        if not isinstance(target, dict):
            target = {}
        result = dict(target)
        for key, value in patch.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = cls._merge(result.get(key), value, depth + 1)
        return result

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
