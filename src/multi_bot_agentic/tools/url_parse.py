"""URL parsing tool.

Agent runs frequently need to reason about a URL relayed between steps: routing
on the host, inspecting a query parameter returned by an upstream system, or
validating that a link is an absolute ``http(s)`` endpoint before following it.
This tool splits a URL into its components using the standard library and
returns them as a canonical JSON object without ever executing code or making a
network request. It returns a structured failure for empty or oversized input,
or for input that is not an absolute URL (missing scheme or host), matching the
calculator, ``json_format``, ``hash``, and ``base64`` tool contracts.
"""

from __future__ import annotations

import json
from typing import Final
from urllib.parse import parse_qs, urlsplit

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 8_000


class UrlParseTool:
    """Split an absolute URL into its structured components."""

    name = "url_parse"
    description = "Splits an absolute URL into scheme, host, port, path, query, and fragment."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse the URL supplied in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the URL to
                parse.

        Returns:
            Tool result whose ``content`` is a canonical JSON object describing
            the URL components, or ``ok=False`` and an explanation when the
            document is empty, too long, or not an absolute URL.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="url is empty",
                metadata={},
            )
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"url exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        try:
            split = urlsplit(document)
        except ValueError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"could not parse url: {error}",
                metadata={},
            )

        if not split.scheme or not split.netloc:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="url is not absolute (missing scheme or host)",
                metadata={"scheme": split.scheme, "netloc": split.netloc},
            )

        try:
            port = split.port
        except ValueError:
            # ``urlsplit`` accepts a non-numeric or out-of-range port lazily and
            # only raises when the ``port`` property is read; surface it as a
            # structured failure rather than propagating.
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="url has an invalid port",
                metadata={"netloc": split.netloc},
            )

        query_params = parse_qs(split.query)
        components: dict[str, object] = {
            "scheme": split.scheme,
            "hostname": split.hostname,
            "port": port,
            "path": split.path,
            "query": split.query,
            "query_params": query_params,
            "fragment": split.fragment,
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(components, indent=2, sort_keys=True, ensure_ascii=False),
            metadata=components,
        )
