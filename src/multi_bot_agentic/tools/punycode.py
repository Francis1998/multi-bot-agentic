"""Punycode / IDNA encode-decode tool.

Agents often need to convert Unicode domain labels to ASCII (xn--) and back.
Models invent Punycode. This tool uses the stdlib ``encodings.idna`` codec
with no network access. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})


class PunycodeTool:
    """Encode Unicode domain text to Punycode/IDNA or decode it back."""

    name = "punycode"
    description = "Encodes or decodes domain text via Punycode/IDNA (mode encode|decode); max 2000 chars; no network."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode the domain text in the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` or ``domain`` argument
                holds the label/domain and whose optional ``mode`` argument
                selects ``encode`` (default) or ``decode``.

        Returns:
            Tool result with the transformed text, or ``ok=False`` on empty,
            oversized, unsupported mode, or codec failure.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("domain")
        if raw is None:
            return self._fail("missing required argument: text or domain", {})
        document = str(raw).strip()
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        try:
            if mode == "encode":
                # idna expects unicode → ascii
                encoded = document.encode("idna").decode("ascii")
                result = encoded
            else:
                result = document.encode("ascii").decode("idna")
        except (UnicodeError, ValueError, LookupError) as exc:
            return self._fail(
                f"punycode {mode} failed: {exc}",
                {"mode": mode},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=result,
            metadata={
                "mode": mode,
                "input_chars": len(document),
                "chars": len(result),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
