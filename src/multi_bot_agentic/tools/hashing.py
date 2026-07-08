"""Cryptographic hashing tool.

Agent runs often need a stable fingerprint of a piece of text: deduplicating
observations, building deterministic cache keys, or verifying that a document
relayed between steps was not mutated. This tool computes a hex digest of the
invocation text using a small allowlist of well-known algorithms. It never
executes code and returns a structured failure for empty or oversized input or
an unsupported algorithm, matching the calculator, ``json_format``, and
``redact`` tool contracts.
"""

from __future__ import annotations

import hashlib
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_ALGORITHM: Final[str] = "sha256"

# An explicit allowlist keeps the tool deterministic and avoids exposing
# platform-dependent or deliberately weakened constructors (for example the
# ``shake_*`` variable-length digests that require a length argument).
_ALGORITHMS: Final[frozenset[str]] = frozenset({"md5", "sha1", "sha256", "sha512"})


class HashTool:
    """Compute a hex digest of a text document."""

    name = "hash"
    description = "Computes a hex digest of text (md5, sha1, sha256, sha512; default sha256)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Compute the digest of the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document to hash and whose optional ``algorithm`` argument
                selects the digest (defaults to ``sha256``).

        Returns:
            Tool result with the hex digest, or ``ok=False`` and an explanation
            when the document is empty or too long, or the algorithm is not
            supported.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
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

        algorithm = str(invocation.arguments.get("algorithm", _DEFAULT_ALGORITHM)).strip().lower()
        if algorithm not in _ALGORITHMS:
            supported = ", ".join(sorted(_ALGORITHMS))
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"unsupported algorithm: {algorithm!r}; supported: {supported}",
                metadata={"algorithm": algorithm},
            )

        encoded = document.encode("utf-8")
        digest = hashlib.new(algorithm, encoded).hexdigest()
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=digest,
            metadata={
                "algorithm": algorithm,
                "chars": len(document),
                "bytes": len(encoded),
            },
        )
