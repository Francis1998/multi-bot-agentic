"""Legacy-only (MCP 2025-11-25 / 2025-06-18) stdio test server; stdlib only.

Requires the ``initialize`` + ``notifications/initialized`` handshake, never
sends ``resultType``, and does not know ``server/discover``: it answers
``-32601`` like real legacy servers, or nothing at all with ``--silent-probe``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SERVER_INFO = {"name": "legacy-fixture", "version": "0.9.0"}
TEXT_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
TOOLS: list[dict[str, Any]] = [
    {"name": "echo", "description": "Echo the text back (legacy).", "inputSchema": TEXT_SCHEMA},
    {"name": "shout", "description": "Upper-case the text.", "inputSchema": TEXT_SCHEMA},
    {"name": "fail", "description": "Always reports a tool execution error.", "inputSchema": {"type": "object"}},
    {"name": "ping_client", "description": "Ping the client before answering.", "inputSchema": {"type": "object"}},
]


class LegacyServer:
    """Single-threaded legacy MCP server state machine."""

    def __init__(self, versions: list[str], silent_probe: bool) -> None:
        self.versions = versions
        self.silent_probe = silent_probe
        self.initialized = False

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method, request_id = request.get("method"), request.get("id")
        params = request.get("params") or {}
        if request_id is None:
            if method == "notifications/initialized":
                self.initialized = True
            return None
        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in self.versions else self.versions[0]
            body = {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": "Legacy fixture for tests.",
            }
            return _result(request_id, body)
        if method == "ping":
            return _result(request_id, {})
        if not self.initialized:
            if self.silent_probe:
                return None
            return _error(request_id, -32601, "Method not found")
        if method == "tools/list":
            return _result(request_id, {"tools": TOOLS})
        if method == "tools/call":
            return self.call_tool(request_id, str(params.get("name")), dict(params.get("arguments") or {}))
        return _error(request_id, -32601, "Method not found")

    def call_tool(self, request_id: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if name == "echo":
            return _text(request_id, str(arguments["text"]))
        if name == "shout":
            return _text(request_id, str(arguments["text"]).upper())
        if name == "fail":
            return _text(request_id, "legacy tool failed", is_error=True)
        if name == "ping_client":
            _write({"jsonrpc": "2.0", "id": "server-ping", "method": "ping"})
            while True:
                line = sys.stdin.readline()
                if not line:
                    return None
                message = json.loads(line)
                if message.get("id") == "server-ping" and "result" in message:
                    return _text(request_id, "client answered ping")
                response = self.handle(message)
                if response is not None:
                    _write(response)
        return _error(request_id, -32602, f"Unknown tool: {name}")


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _result(request_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": body}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text(request_id: Any, text: str, *, is_error: bool = False) -> dict[str, Any]:
    return _result(request_id, {"content": [{"type": "text", "text": text}], "isError": is_error})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", default="2025-11-25,2025-06-18", help="comma-separated supported versions")
    parser.add_argument("--silent-probe", action="store_true", help="ignore requests sent before initialization")
    args = parser.parse_args()
    server = LegacyServer(args.versions.split(","), args.silent_probe)
    print("legacy fixture ready", file=sys.stderr, flush=True)
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        if not line.strip():
            continue
        response = server.handle(json.loads(line))
        if response is not None:
            _write(response)


if __name__ == "__main__":
    main()
