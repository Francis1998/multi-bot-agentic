"""Modern-only (MCP 2026-07-28) stdio test server; stdlib only.

Speaks the stateless revision: answers ``server/discover``, requires the
per-request ``_meta`` envelope, rejects ``initialize`` (naming the versions it
supports), and returns ``-32022`` for unsupported versions. Test tools cover
success, ``isError``, timeouts, large and binary output, PII, and crashes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any

SUPPORTED = ["2026-07-28"]
SERVER_INFO = {"name": "modern-fixture", "version": "1.0.0"}
META = "io.modelcontextprotocol/"
PAGE_SIZE = 3
# Grandchild that ignores SIGTERM and inherits the stdio pipes, like a stubborn npx -> node child.
STUBBORN_CHILD = (
    "import os, signal, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
    "time.sleep(60)\n"
)


def _schema(properties: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {key: {"type": value} for key, value in properties.items()},
        "required": required,
    }


TOOLS: list[dict[str, Any]] = [
    {"name": "echo", "description": "Echo the text back.", "inputSchema": _schema({"text": "string"}, ["text"])},
    {"name": "add", "description": "Add numbers.", "inputSchema": _schema({"a": "number", "b": "number"}, ["a", "b"])},
    {"name": "fail", "description": "Always reports a tool execution error.", "inputSchema": _schema({}, [])},
    {"name": "sleep", "description": "Sleep, then answer.", "inputSchema": _schema({"seconds": "number"}, ["seconds"])},
    {"name": "big", "description": "Return a large text block.", "inputSchema": _schema({"size": "integer"}, ["size"])},
    {"name": "image", "description": "Return an image with a caption.", "inputSchema": _schema({}, [])},
    {"name": "contact", "description": "Return contact details.", "inputSchema": _schema({}, [])},
    {"name": "crash", "description": "Exit without answering.", "inputSchema": _schema({}, [])},
    {"name": "surrogate", "description": "Return text with a lone surrogate.", "inputSchema": _schema({}, [])},
    {"name": "weird_type", "description": "Return blocks with hostile types.", "inputSchema": _schema({}, [])},
    {"name": "close_stdin", "description": "Close stdin but keep running.", "inputSchema": _schema({}, [])},
    {"name": "bad name:x", "description": "Invalid name that clients must skip.", "inputSchema": _schema({}, [])},
]


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _result(request_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    payload = {**body, "resultType": "complete", "_meta": {f"{META}serverInfo": SERVER_INFO}}
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _text(request_id: Any, text: str, *, is_error: bool = False) -> dict[str, Any]:
    return _result(request_id, {"content": [{"type": "text", "text": text}], "isError": is_error})


def _call_tool(request_id: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "echo":
        return _text(request_id, str(arguments["text"]))
    if name == "add":
        total = arguments["a"] + arguments["b"]
        body = {"content": [{"type": "text", "text": str(total)}], "structuredContent": {"sum": total}}
        return _result(request_id, body)
    if name == "fail":
        return _text(request_id, f"tool failed: {arguments.get('reason', 'by design')}", is_error=True)
    if name == "sleep":
        time.sleep(float(arguments["seconds"]))
        return _text(request_id, "awake")
    if name == "big":
        return _text(request_id, "é" * int(arguments["size"]))
    if name == "image":
        blocks = [{"type": "image", "data": "iVBORw0KGgo=", "mimeType": "image/png"}, {"type": "text", "text": "a dot"}]
        return _result(request_id, {"content": blocks})
    if name == "contact":
        return _text(request_id, "mail alice@example.com, key sk-abcdefghijklmnop1234")
    if name == "surrogate":
        return _text(request_id, "bad \ud800 text")
    if name == "weird_type":
        return _result(request_id, {"content": [{"type": "sk-abcdefghijklmnopqrstuv"}, {"type": "x" * 5000}]})
    if name == "close_stdin":
        os.close(0)
        _write(_text(request_id, "stdin closed"))
        time.sleep(30)
        sys.exit(0)
    if name == "crash":
        print("crashing on purpose", file=sys.stderr, flush=True)
        sys.exit(3)
    return _error(request_id, -32602, f"Unknown tool: {name}")


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method, request_id = request.get("method"), request.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        return _error(request_id, -32601, f"initialize is not supported; supported versions: {', '.join(SUPPORTED)}")
    params = request.get("params") or {}
    meta = params.get("_meta")
    if not isinstance(meta, dict) or f"{META}protocolVersion" not in meta or f"{META}clientCapabilities" not in meta:
        return _error(request_id, -32602, "missing required _meta envelope")
    version = meta[f"{META}protocolVersion"]
    if version not in SUPPORTED:
        data = {"supported": SUPPORTED, "requested": version}
        return _error(request_id, -32022, "Unsupported protocol version", data)
    if method == "server/discover":
        body = {
            "supportedVersions": SUPPORTED,
            "capabilities": {"tools": {}},
            "instructions": "Modern fixture for tests.",
            "ttlMs": 60000,
            "cacheScope": "public",
        }
        return _result(request_id, body)
    if method == "tools/list":
        start = int(params.get("cursor") or 0)
        page: dict[str, Any] = {"tools": TOOLS[start : start + PAGE_SIZE], "ttlMs": 60000, "cacheScope": "public"}
        if start + PAGE_SIZE < len(TOOLS):
            page["nextCursor"] = str(start + PAGE_SIZE)
        return _result(request_id, page)
    if method == "tools/call":
        return _call_tool(request_id, str(params.get("name")), dict(params.get("arguments") or {}))
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slow-start", type=float, default=0.0, help="seconds to wait before reading stdin")
    parser.add_argument("--spawn-child", default=None, help="spawn a SIGTERM-ignoring child that writes its pid here")
    args = parser.parse_args()
    if args.spawn_child:
        subprocess.Popen([sys.executable, "-c", STUBBORN_CHILD, args.spawn_child])
    time.sleep(args.slow_start)
    print("modern fixture ready", file=sys.stderr, flush=True)
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        if not line.strip():
            continue
        response = _handle(json.loads(line))
        if response is not None:
            _write(response)


if __name__ == "__main__":
    main()
