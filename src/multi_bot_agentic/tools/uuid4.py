"""Random UUID (version 4) generation tool.

Agent runs sometimes need a fresh opaque identifier for a correlation id,
temporary handle, or client-side token that must not collide with prior steps.
Unlike ``uuid5`` (deterministic hash of namespace + name), a version-4 UUID is
drawn from random bits via the standard library. It is suitable as an opaque
identifier, not as a cryptographic secret or keying material — see the user
guide for the non-crypto note. This tool never executes code and never makes a
network request. Empty-or-invalid ``count`` and oversized requests return
structured failures matching the ``uuid5``, ``hash``, and ``slugify`` contracts.
"""

from __future__ import annotations

import uuid
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MIN_COUNT: Final[int] = 1
_MAX_COUNT: Final[int] = 16
_DEFAULT_COUNT: Final[int] = 1


class Uuid4Tool:
    """Generate one or more random version-4 UUIDs."""

    name = "uuid4"
    description = (
        "Generates random UUIDv4 identifier(s); optional count 1-16 (default 1). "
        "Opaque ids only — not for cryptographic secrets."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Generate random version-4 UUID(s).

        Args:
            invocation: Tool invocation whose optional ``count`` argument selects
                how many UUIDs to generate (integer 1..16; default 1).

        Returns:
            Tool result whose ``content`` is a single UUID string when
            ``count`` is 1, or newline-joined UUID strings when ``count`` is
            greater than 1; ``ok=False`` with an explanation when ``count`` is
            missing-as-invalid or out of bounds.
        """

        count, error = _resolve_count(invocation.arguments.get("count", _DEFAULT_COUNT))
        if error is not None:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=error,
                metadata={"count": invocation.arguments.get("count")},
            )

        values = [str(uuid.uuid4()) for _ in range(count)]
        content = values[0] if count == 1 else "\n".join(values)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "count": count,
                "version": 4,
                "uuids": values,
            },
        )


def _resolve_count(raw: object) -> tuple[int, str | None]:
    """Parse and bound the optional ``count`` argument.

    Args:
        raw: Caller-supplied count value.

    Returns:
        ``(count, error)`` — exactly one of a valid count or an error message.
    """

    message = f"count must be an integer {_MIN_COUNT}..{_MAX_COUNT}"
    if isinstance(raw, bool) or raw is None:
        return 0, message
    if isinstance(raw, int):
        value = raw
    else:
        text = str(raw).strip()
        if not text.isdigit():
            return 0, message
        value = int(text)

    if value < _MIN_COUNT or value > _MAX_COUNT:
        return 0, message
    return value, None
