"""Deterministic namespaced UUID (version 5) tool.

Agent runs frequently need a *stable* identifier derived from a piece of text:
a deterministic primary key for an observation, an idempotency key for a
downstream call, or a reproducible correlation id shared across steps. Unlike a
random UUID (version 4), a version-5 UUID is a SHA-1 hash of a namespace plus a
name, so the same ``(namespace, name)`` pair always yields the same id \u2014 which
keeps the surrounding agent runtime deterministic. This tool computes that id
using the standard library, never executes code, and never makes a network
request. It returns a structured failure for empty or oversized input or an
unusable namespace, matching the ``hash``, ``base64``, ``json_format``, and
``url_parse`` tool contracts.
"""

from __future__ import annotations

import uuid
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 8_000
_DEFAULT_NAMESPACE: Final[str] = "dns"

# The four RFC 4122 predefined namespaces, keyed by a short lowercase alias. A
# caller may also pass any custom UUID string as the namespace.
_PREDEFINED_NAMESPACES: Final[dict[str, uuid.UUID]] = {
    "dns": uuid.NAMESPACE_DNS,
    "url": uuid.NAMESPACE_URL,
    "oid": uuid.NAMESPACE_OID,
    "x500": uuid.NAMESPACE_X500,
}


class Uuid5Tool:
    """Compute a deterministic version-5 UUID from a namespace and a name."""

    name = "uuid5"
    description = (
        "Computes a deterministic UUIDv5 from a name and namespace "
        "(dns, url, oid, x500, or a custom UUID; default dns)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Compute the version-5 UUID for the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the name to
                hash and whose optional ``namespace`` argument selects the
                namespace (one of ``dns``, ``url``, ``oid``, ``x500``, or a
                custom UUID string; defaults to ``dns``).

        Returns:
            Tool result whose ``content`` is the canonical UUID string, or
            ``ok=False`` and an explanation when the name is empty or too long,
            or the namespace is not usable.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="name is empty",
                metadata={},
            )
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"name exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        namespace_arg = str(invocation.arguments.get("namespace", _DEFAULT_NAMESPACE)).strip()
        namespace = _resolve_namespace(namespace_arg)
        if namespace is None:
            supported = ", ".join(sorted(_PREDEFINED_NAMESPACES))
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=(f"unusable namespace: {namespace_arg!r}; supported: {supported}, or a custom UUID string"),
                metadata={"namespace": namespace_arg},
            )

        computed = uuid.uuid5(namespace, document)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=str(computed),
            metadata={
                "namespace": str(namespace),
                "name": document,
                "version": computed.version,
            },
        )


def _resolve_namespace(namespace_arg: str) -> uuid.UUID | None:
    """Resolve a namespace argument to a concrete UUID.

    A short lowercase alias (``dns``/``url``/``oid``/``x500``) selects one of the
    RFC 4122 predefined namespaces; any other value is treated as a custom UUID
    string.

    Args:
        namespace_arg: Namespace alias or custom UUID string.

    Returns:
        The resolved namespace UUID, or ``None`` when the value is neither a
        known alias nor a valid UUID string.
    """

    alias = _PREDEFINED_NAMESPACES.get(namespace_arg.lower())
    if alias is not None:
        return alias
    try:
        return uuid.UUID(namespace_arg)
    except ValueError:
        return None
