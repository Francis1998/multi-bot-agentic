"""Tiny MCP 2026-07-28 (modern, stateless) stdio server used by the MCP tools demo.

Run it through multi-bot-agentic rather than by hand::

    multi-bot-agentic mcp-tools --mcp-config examples/mcp/mcp.json

It exposes two read-only tools over newline-delimited JSON-RPC on stdin/stdout
(logs go to stderr only, as the stdio transport requires):

- ``search_notes(query, limit=3)``: keyword search over a few in-memory notes.
- ``word_count(text)``: count the words in a text.
"""

from __future__ import annotations

import json
import sys
from typing import Any

PROTOCOL_VERSIONS = ["2026-07-28"]
SERVER_INFO = {"name": "notes-demo", "version": "1.0.0"}
META = "io.modelcontextprotocol/"

NOTES = {
    "release-checklist": "Release checklist: freeze main, run the eval suite, tag the build, update the CHANGELOG.",
    "incident-runbook": "Incident runbook: page the on-call, open a status page, capture the event log for replay.",
    "mcp-rollout": "MCP rollout: start with read-only servers, allowlist tools, cap result bytes, review the log.",
}

TOOLS = [
    {
        "name": "search_notes",
        "title": "Search notes",
        "description": "Search the demo team notes by keyword and return matching note titles and text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to look for"},
                "limit": {"type": "integer", "description": "Maximum matches (default 3)"},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "word_count",
        "title": "Word count",
        "description": "Count the words in a text.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "annotations": {"readOnlyHint": True},
    },
]


def respond(request_id: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> None:
    """Write one JSON-RPC response line to stdout."""

    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        message["error"] = error
    else:
        message["result"] = {**(result or {}), "resultType": "complete", "_meta": {f"{META}serverInfo": SERVER_INFO}}
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run a tool and return a CallToolResult body."""

    if name == "search_notes":
        query = str(arguments.get("query", "")).strip().lower()
        limit = int(arguments.get("limit", 3))
        words = [word for word in query.split() if len(word) > 2] or [query]
        matches = [
            {"title": title, "text": text}
            for title, text in NOTES.items()
            if any(word in f"{title} {text}".lower() for word in words)
        ][:limit]
        if not matches:
            return {"content": [{"type": "text", "text": f"no notes match {query!r}"}], "isError": True}
        lines = [f"{match['title']}: {match['text']}" for match in matches]
        return {"content": [{"type": "text", "text": "\n".join(lines)}], "structuredContent": {"matches": matches}}
    if name == "word_count":
        count = len(str(arguments.get("text", "")).split())
        return {"content": [{"type": "text", "text": f"{count} words"}], "structuredContent": {"words": count}}
    raise KeyError(name)


def handle(request: dict[str, Any]) -> None:
    """Serve one request statelessly: every request carries its own ``_meta``."""

    request_id, method = request.get("id"), request.get("method")
    if request_id is None:
        return
    params = request.get("params") or {}
    version = (params.get("_meta") or {}).get(f"{META}protocolVersion")
    if version is None:
        respond(request_id, error={"code": -32602, "message": f"missing _meta; this server speaks {PROTOCOL_VERSIONS}"})
    elif version not in PROTOCOL_VERSIONS:
        data = {"supported": PROTOCOL_VERSIONS, "requested": version}
        respond(request_id, error={"code": -32022, "message": "Unsupported protocol version", "data": data})
    elif method == "server/discover":
        body = {"supportedVersions": PROTOCOL_VERSIONS, "capabilities": {"tools": {}}, "ttlMs": 3_600_000}
        respond(request_id, {**body, "cacheScope": "public", "instructions": "Read-only demo notes."})
    elif method == "tools/list":
        respond(request_id, {"tools": TOOLS, "ttlMs": 3_600_000, "cacheScope": "public"})
    elif method == "tools/call":
        try:
            respond(request_id, call_tool(str(params.get("name")), dict(params.get("arguments") or {})))
        except KeyError:
            respond(request_id, error={"code": -32602, "message": f"Unknown tool: {params.get('name')}"})
    else:
        respond(request_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> None:
    """Serve requests until stdin closes."""

    print("notes-demo MCP server ready (stdio, 2026-07-28)", file=sys.stderr, flush=True)
    for line in iter(sys.stdin.readline, ""):
        if line.strip():
            handle(json.loads(line))


if __name__ == "__main__":
    main()
