"""ULID generate / validate tool.

Agents needing sortable unique IDs often invent UUID variants. This tool
generates Crockford-Base32 ULIDs or validates existing ones with no network
access. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import os
import time
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "generate"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"generate", "validate"})
_CROCKFORD: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_SET: Final[frozenset[str]] = frozenset(_CROCKFORD)
_ULID_LENGTH: Final[int] = 26


class UlidTool:
    """Generate or validate Crockford-Base32 ULIDs."""

    name = "ulid"
    description = (
        "Generates a Crockford-Base32 ULID or validates an existing one "
        "(mode generate|validate); max 2000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Generate or validate a ULID.

        Args:
            invocation: Tool invocation whose optional ``mode`` selects
                ``generate`` (default) or ``validate``. Validate mode reads
                ``text`` / ``ulid`` / ``value``.

        Returns:
            Tool result with a new ULID string or ``true``/``false``;
            ``ok=False`` on errors.
        """

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        if mode == "generate":
            value = _generate_ulid()
            return ToolResult(
                tool_name=self.name,
                ok=True,
                content=value,
                metadata={"mode": mode, "length": len(value), "ulid": value},
            )

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("ulid")
        if raw is None:
            raw = invocation.arguments.get("value")
        if raw is None:
            return self._fail("missing required argument: text, ulid, or value", {"mode": mode})
        document = str(raw).strip()
        if not document:
            return self._fail("text is empty", {"mode": mode})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document), "mode": mode},
            )
        valid = _is_ulid(document)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content="true" if valid else "false",
            metadata={
                "mode": mode,
                "length": len(document),
                "valid": valid,
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _encode_crockford(value: int, length: int) -> str:
    """Encode a non-negative integer as fixed-length Crockford Base32."""

    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def _generate_ulid() -> str:
    """Return a new ULID (48-bit timestamp + 80-bit randomness)."""

    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode_crockford(timestamp_ms, 10) + _encode_crockford(randomness, 16)


def _is_ulid(candidate: str) -> bool:
    """Return whether ``candidate`` is a Crockford-Base32 ULID of length 26."""

    text = candidate.strip().upper().replace("O", "0").replace("I", "1").replace("L", "1")
    if len(text) != _ULID_LENGTH:
        return False
    return all(ch in _CROCKFORD_SET for ch in text)
