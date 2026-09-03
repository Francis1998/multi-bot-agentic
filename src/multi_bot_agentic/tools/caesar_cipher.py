"""Caesar cipher tool.

Agents demonstrating classical ciphers need a deterministic Caesar shift.
Models miscalculate letter wrapping. This tool shifts alphabetic characters
by a configurable amount with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 20_000


class CaesarCipherTool:
    """Shift alphabetic characters by a configurable amount."""

    name = "caesar_cipher"
    description = (
        "Applies a Caesar cipher shift to text (default shift 13); preserves "
        "upper/lower case; non-alpha chars pass through; max 20000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        raw = invocation.arguments.get("text")
        if raw is None:
            return self._fail("missing required argument: text", {})
        document = str(raw).strip()
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_CHARS}",
                {"chars": len(document)},
            )

        shift_raw = invocation.arguments.get("shift", 13)
        if not isinstance(shift_raw, int):
            try:
                shift_raw = int(shift_raw)
            except (TypeError, ValueError):
                return self._fail(
                    f"shift must be an integer, got {type(shift_raw).__name__}",
                    {},
                )
        assert isinstance(shift_raw, int)
        shift = shift_raw % 26

        result = self._shift(document, shift)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=result,
            metadata={"shift": shift_raw, "chars": len(document)},
        )

    @staticmethod
    def _shift(text: str, shift: int) -> str:
        out: list[str] = []
        for ch in text:
            if ch.isascii() and ch.isalpha():
                base = ord("A") if ch.isupper() else ord("a")
                out.append(chr((ord(ch) - base + shift) % 26 + base))
            else:
                out.append(ch)
        return "".join(out)

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
