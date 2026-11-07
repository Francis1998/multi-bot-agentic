"""Dependency-free stdio MCP client that speaks both protocol eras.

The client launches a server as a subprocess and exchanges newline-delimited
JSON-RPC messages over stdin/stdout; stderr is drained into a small
diagnostics buffer. Era detection follows the MCP 2026-07-28 versioning rules
for stdio:

1. Probe with ``server/discover`` carrying the per-request ``_meta`` envelope.
   A ``DiscoverResult`` means the server is *modern*; an
   ``UnsupportedProtocolVersionError`` (``-32022``) means it is modern but
   wants another version, so the probe is retried with a mutually supported
   one. Modern requests always repeat the ``_meta`` envelope and there is no
   handshake.
2. Any other error, or no answer within the probe timeout, means the server is
   *legacy*: fall back to ``initialize`` + ``notifications/initialized``
   (2025-11-25 and earlier). If the probe answer arrives late (a slow-starting
   modern server) and ``initialize`` is rejected, the client switches back to
   the modern era instead of failing.

The detected era is cached for the lifetime of the server process and
re-detected only when a crashed server is restarted.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import weakref
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata
from itertools import count
from pathlib import Path
from typing import IO, Any

MODERN_PROTOCOL_VERSIONS: tuple[str, ...] = ("2026-07-28",)
LEGACY_PROTOCOL_VERSIONS: tuple[str, ...] = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
UNSUPPORTED_PROTOCOL_VERSION = -32022
# HeaderMismatch, MissingRequiredClientCapability, UnsupportedProtocolVersion.
_RECOGNIZED_MODERN_ERRORS = frozenset({-32020, -32021, UNSUPPORTED_PROTOCOL_VERSION})
_META = "io.modelcontextprotocol/"
DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0
DEFAULT_PROBE_TIMEOUT_SECONDS = 5.0
_MAX_MESSAGE_BYTES = 16 * 1024 * 1024
_MAX_LIST_PAGES = 64
_SHUTDOWN_GRACE_SECONDS = 2.0
_NOTIFY_TIMEOUT_SECONDS = 1.0
_REPLY_TIMEOUT_SECONDS = 5.0
_STDERR_TAIL_LINES = 40


def _client_version() -> str:
    """Return the installed package version for ``clientInfo``."""

    try:
        return metadata.version("multi-bot-agentic")
    except metadata.PackageNotFoundError:
        return "0+unknown"


CLIENT_INFO: dict[str, str] = {"name": "multi-bot-agentic", "version": _client_version()}


class McpEra(str, Enum):
    """MCP protocol era detected for a server process.

    Note:
        Exposed as ``(str, Enum)`` so Python 3.10 CI stays green (``StrEnum`` is 3.11+).
    """

    MODERN = "modern"
    LEGACY = "legacy"


class McpError(RuntimeError):
    """Base class for MCP client failures."""


class McpTransportError(McpError):
    """The server could not be launched, exited, or broke the stdio framing."""


class McpTimeoutError(McpError):
    """The server did not answer within the configured timeout."""


class McpProtocolError(McpError):
    """The server answered with a JSON-RPC error or an invalid result.

    Attributes:
        code: JSON-RPC error code, when the server sent one.
        data: Optional JSON-RPC error data.
    """

    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class McpVersionError(McpProtocolError):
    """Client and server share no protocol version."""


@dataclass(frozen=True)
class McpToolInfo:
    """Tool definition returned by ``tools/list``.

    Attributes:
        name: Tool name, unique within its server.
        description: Human-readable description (may be empty).
        input_schema: JSON Schema for the tool arguments.
        title: Optional display title.
        annotations: Optional behavior hints; untrusted unless the server is trusted.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    title: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class McpCallResult:
    """Normalized ``tools/call`` result.

    Attributes:
        content: Content blocks (text, image, audio, resource_link, resource).
        is_error: True when the server reported a tool execution error.
        structured_content: Optional ``structuredContent`` value.
    """

    content: tuple[dict[str, Any], ...]
    is_error: bool
    structured_content: Any = None


class StdioMcpClient:
    """Stdio MCP client with dual-era (2026-07-28 / legacy) protocol detection.

    The client is safe to share between threads for requests; process restarts
    are serialized. Use it as a context manager or call :meth:`close` so the
    server process tree is always terminated.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        name: str = "mcp",
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
        probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
        modern_versions: Sequence[str] = MODERN_PROTOCOL_VERSIONS,
        legacy_versions: Sequence[str] = LEGACY_PROTOCOL_VERSIONS,
        max_restarts: int = 1,
    ) -> None:
        """Configure (but do not launch) a server.

        Args:
            command: Executable followed by its arguments.
            name: Server name used in error messages.
            env: Complete environment for the server process (``None`` inherits).
            cwd: Working directory for the server process.
            startup_timeout_seconds: Budget for launch plus era detection.
            probe_timeout_seconds: How long the ``server/discover`` probe may stay unanswered
                before falling back to the legacy handshake.
            modern_versions: Modern protocol versions in preference order.
            legacy_versions: Legacy protocol versions in preference order.
            max_restarts: Restarts allowed after the server exits unexpectedly.

        Raises:
            ValueError: If the command or version lists are empty.
        """

        if not command or not command[0]:
            raise ValueError("command must name an executable")
        if not modern_versions and not legacy_versions:
            raise ValueError("at least one protocol version is required")
        self.name = name
        self._command = tuple(command)
        self._env = None if env is None else dict(env)
        self._cwd = cwd
        self._startup_timeout = startup_timeout_seconds
        self._probe_timeout = probe_timeout_seconds
        self._modern_versions = tuple(modern_versions)
        self._legacy_versions = tuple(legacy_versions)
        self._max_restarts = max_restarts
        self._restarts = 0
        self._ids = count(1)
        self._cond = threading.Condition()
        self._write_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._readers: tuple[threading.Thread, ...] = ()
        self._finalizer: weakref.finalize[Any, Any] | None = None
        self._pending: dict[int, int] = {}
        self._responses: dict[int, dict[str, Any]] = {}
        self._closed_reason: str | None = None
        self._generation = 0
        self._legacy_mode = False
        self._launched = False
        self._user_closed = False
        self._stderr_tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
        self._stderr_lock = threading.Lock()
        self.era: McpEra | None = None
        self.protocol_version: str | None = None
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self.instructions: str | None = None

    def __enter__(self) -> StdioMcpClient:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def pid(self) -> int | None:
        """Return the server process id while it is running."""

        process = self._process
        return process.pid if process is not None else None

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        """Return the most recent server stderr lines (diagnostics only)."""

        with self._stderr_lock:
            return tuple(self._stderr_tail)

    def start(self) -> None:
        """Launch the server if needed and detect its protocol era.

        Raises:
            McpError: If the server cannot be launched or speaks no shared version.
        """

        with self._lifecycle_lock:
            if self._user_closed:
                raise McpTransportError(f"MCP client for '{self.name}' is closed")
            if self._is_running():
                return
            self._launch()

    def list_tools(self, timeout_seconds: float = 30.0) -> list[McpToolInfo]:
        """Return every tool the server exposes, following pagination.

        Args:
            timeout_seconds: Per-page request timeout.

        Returns:
            Tools in server order; entries without a string ``name`` are dropped.

        Raises:
            McpError: On transport, timeout, or protocol failures.
        """

        self._ensure_running()
        if "tools" not in self.capabilities:
            return []
        tools: list[McpToolInfo] = []
        cursor: str | None = None
        for _ in range(_MAX_LIST_PAGES):
            params: dict[str, Any] = {} if cursor is None else {"cursor": cursor}
            result = self._call("tools/list", params, timeout_seconds)
            raw_tools = result.get("tools", [])
            if not isinstance(raw_tools, list):
                raise McpProtocolError("tools/list returned a non-list 'tools' field")
            tools.extend(info for info in map(_parse_tool, raw_tools) if info is not None)
            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                return tools
            cursor = next_cursor
        raise McpProtocolError(f"tools/list did not finish within {_MAX_LIST_PAGES} pages")

    def call_tool(self, name: str, arguments: Mapping[str, Any], timeout_seconds: float = 30.0) -> McpCallResult:
        """Invoke a tool.

        Args:
            name: Tool name as reported by the server.
            arguments: JSON-serializable tool arguments.
            timeout_seconds: Request timeout; on expiry the request is cancelled.

        Returns:
            Normalized tool result (``is_error`` reports tool execution errors).

        Raises:
            McpError: On transport, timeout, or protocol (JSON-RPC) failures.
        """

        self._ensure_running()
        result = self._call("tools/call", {"name": name, "arguments": dict(arguments)}, timeout_seconds)
        content = result.get("content", [])
        if not isinstance(content, list):
            raise McpProtocolError("tools/call returned a non-list 'content' field")
        return McpCallResult(
            content=tuple(item for item in content if isinstance(item, dict)),
            is_error=result.get("isError") is True,
            structured_content=result.get("structuredContent"),
        )

    def close(self) -> None:
        """Shut the server down (close stdin, then SIGTERM/SIGKILL its process group)."""

        with self._lifecycle_lock:
            self._user_closed = True
            self._teardown()

    def _is_running(self) -> bool:
        """Return whether the process is alive with an intact stdio channel."""

        process = self._process
        return process is not None and process.poll() is None and self._closed_reason is None

    def _ensure_running(self) -> None:
        """Start the server on first use and restart it (bounded) after a crash."""

        with self._lifecycle_lock:
            if self._user_closed:
                raise McpTransportError(f"MCP client for '{self.name}' is closed")
            if self._is_running():
                return
            if self._launched:
                if self._restarts >= self._max_restarts:
                    reason = self._closed_reason or "server process exited"
                    raise McpTransportError(self._describe(f"MCP server '{self.name}' is unavailable: {reason}"))
                self._restarts += 1
            self._launch()

    def _launch(self) -> None:
        """Spawn a fresh process and detect its era; clean up on failure."""

        self._teardown()
        self._launched = True
        self._spawn()
        try:
            self._negotiate(time.monotonic() + self._startup_timeout, allow_legacy=True)
        except BaseException:
            self._teardown()
            raise

    def _spawn(self) -> None:
        """Start the subprocess and its stdout/stderr reader threads."""

        with self._cond:
            self._pending.clear()
            self._responses.clear()
            self._closed_reason = None
            self._generation += 1
            generation = self._generation
            self._cond.notify_all()  # waiters of the replaced process fail fast in _await
        self._legacy_mode = False
        self.era = None
        self.protocol_version = None
        self.server_info = {}
        self.capabilities = {}
        self.instructions = None
        try:
            process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                cwd=self._cwd,
                start_new_session=sys.platform != "win32",
            )
        except OSError as error:
            raise McpTransportError(f"cannot start MCP server '{self.name}' ({self._command[0]}): {error}") from error
        self._process = process
        self._finalizer = weakref.finalize(self, _shutdown_process, process, 0.5)
        stdin, stdout, stderr = process.stdin, process.stdout, process.stderr
        if stdin is None or stdout is None or stderr is None:
            raise McpTransportError(f"MCP server '{self.name}' has no stdio pipes")
        if sys.platform != "win32":
            # Writes go through os.write with a deadline, so a server that stops reading stdin
            # can never block a request, a cancellation, or shutdown.
            os.set_blocking(stdin.fileno(), False)
        readers = (
            threading.Thread(
                target=self._read_stdout, args=(stdout, generation), name=f"mcp-{self.name}-out", daemon=True
            ),
            threading.Thread(target=self._read_stderr, args=(stderr,), name=f"mcp-{self.name}-err", daemon=True),
        )
        for reader in readers:
            reader.start()
        self._readers = readers

    def _teardown(self) -> None:
        """Terminate the current process tree, if any, and release its pipes."""

        process, self._process = self._process, None
        if self._finalizer is not None:
            self._finalizer.detach()
            self._finalizer = None
        if process is None:
            return
        if self._write_lock.acquire(timeout=_SHUTDOWN_GRACE_SECONDS):
            try:
                _close_quietly(process.stdin)
            finally:
                self._write_lock.release()
        _shutdown_process(process, _SHUTDOWN_GRACE_SECONDS, close_stdin=False)
        for reader in self._readers:
            reader.join(timeout=1.0)
        if not any(reader.is_alive() for reader in self._readers):
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        self._readers = ()
        with self._cond:
            if self._closed_reason is None:
                self._closed_reason = "server stopped"
            self._cond.notify_all()

    def _read_stdout(self, stream: IO[bytes], generation: int) -> None:
        """Reader thread: route responses to waiters until EOF or a framing error.

        ``generation`` ties the thread to one spawned process, so a reader that
        outlives a restart can never mark the replacement process as closed.
        """

        reason = "server closed its stdout"
        try:
            while True:
                raw = stream.readline(_MAX_MESSAGE_BYTES + 1)
                if not raw:
                    break
                if len(raw) > _MAX_MESSAGE_BYTES and not raw.endswith(b"\n"):
                    reason = f"server sent a message larger than {_MAX_MESSAGE_BYTES} bytes"
                    break
                self._handle_line(raw)
        except (OSError, ValueError, RecursionError) as error:
            reason = f"reading server stdout failed: {error}"
        with self._cond:
            if generation == self._generation and self._closed_reason is None:
                self._closed_reason = reason
            self._cond.notify_all()

    def _read_stderr(self, stream: IO[bytes]) -> None:
        """Reader thread: keep the last stderr lines for diagnostics (never parsed)."""

        try:
            for raw in iter(lambda: stream.readline(4096), b""):
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    with self._stderr_lock:
                        self._stderr_tail.append(line[:500])
        except (OSError, ValueError):
            return

    def _handle_line(self, raw: bytes) -> None:
        """Dispatch one newline-delimited JSON-RPC message from the server."""

        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            with self._stderr_lock:
                self._stderr_tail.append(f"[ignored non-JSON stdout line] {text[:200]}")
            return
        if not isinstance(message, dict):
            return
        if "method" in message:
            if "id" in message:
                self._answer_server_request(message)
            return
        request_id = _coerce_id(message.get("id"))
        if request_id is None:
            return
        with self._cond:
            if request_id in self._pending:
                self._responses[request_id] = message
                self._cond.notify_all()

    def _answer_server_request(self, message: dict[str, Any]) -> None:
        """Answer legacy server-to-client requests; modern stdio forbids client responses."""

        if not self._legacy_mode:
            return
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        if message.get("method") == "ping":
            reply["result"] = {}
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        try:
            self._write(reply, time.monotonic() + _REPLY_TIMEOUT_SECONDS, self._generation)
        except McpError:
            return

    def _write(self, message: dict[str, Any], deadline: float, generation: int) -> None:
        """Serialize one message as a single line on the server's stdin, giving up at ``deadline``.

        ``generation`` is the server process the message belongs to; if that process
        was replaced in the meantime the message is rejected instead of being sent
        to the replacement (which could run a tool the caller believes failed).

        Raises:
            McpTimeoutError: If the server does not drain its stdin in time; the
                channel is then marked broken because a partial line may have been sent.
            McpTransportError: If the server is gone or was restarted.
        """

        try:
            # ASCII-only JSON (non-ASCII as \\u escapes) can always be encoded, even with lone surrogates.
            data = (json.dumps(message, allow_nan=False, separators=(",", ":")) + "\n").encode("ascii")
        except (TypeError, ValueError, RecursionError) as error:
            raise McpProtocolError(f"cannot encode MCP message: {error}") from error
        with self._cond:
            current_generation, process = self._generation, self._process
        if current_generation != generation:
            raise McpTransportError(f"MCP server '{self.name}' restarted before the message was sent")
        stdin = process.stdin if process is not None else None
        if stdin is None:
            raise McpTransportError(f"MCP server '{self.name}' is not running")
        if not self._write_lock.acquire(timeout=_remaining(deadline)):
            raise McpTimeoutError(f"MCP server '{self.name}' is not accepting input (another write is stalled)")
        try:
            completed = _write_all(stdin, data, deadline)
        except (OSError, ValueError) as error:
            self._mark_broken(f"cannot write to the server's stdin: {error}", generation)
            raise McpTransportError(self._describe(f"cannot write to MCP server '{self.name}': {error}")) from error
        finally:
            self._write_lock.release()
        if not completed:
            self._mark_broken("server stopped reading its stdin", generation)
            raise McpTimeoutError(f"MCP server '{self.name}' stopped reading its stdin")

    def _mark_broken(self, reason: str, generation: int) -> None:
        """Fail waiters and force a restart before the channel of ``generation`` is reused.

        A failure observed on an already-replaced process is ignored, so an old
        write can never invalidate its replacement.
        """

        with self._cond:
            if generation == self._generation and self._closed_reason is None:
                self._closed_reason = reason
            self._cond.notify_all()

    def _notify(self, method: str, params: dict[str, Any] | None = None, *, deadline: float | None = None) -> None:
        """Send a best-effort notification (bounded so it can never block)."""

        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params:
            message["params"] = params
        try:
            write_deadline = time.monotonic() + _NOTIFY_TIMEOUT_SECONDS if deadline is None else deadline
            self._write(message, write_deadline, self._generation)
        except McpError:
            return

    def _issue(self, method: str, params: dict[str, Any], deadline: float) -> int:
        """Register and send a request (write bounded by ``deadline``), returning its id."""

        request_id = next(self._ids)
        with self._cond:
            generation = self._generation
            self._pending[request_id] = generation
        try:
            self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, deadline, generation)
        except BaseException:
            self._forget(request_id)
            raise
        return request_id

    def _await(self, request_id: int, timeout: float) -> dict[str, Any] | None:
        """Wait for a response; ``None`` on timeout (the request stays registered).

        Raises:
            McpTransportError: If the server's stdout closed before the response arrived.
        """

        deadline = time.monotonic() + max(0.0, timeout)
        with self._cond:
            while True:
                message = self._responses.pop(request_id, None)
                if message is not None:
                    return message
                if self._pending.get(request_id) != self._generation:
                    raise McpTransportError(f"MCP server '{self.name}' restarted while a request was pending")
                if self._closed_reason is not None:
                    raise McpTransportError(self._describe(f"MCP server '{self.name}': {self._closed_reason}"))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)

    def _forget(self, request_id: int) -> None:
        """Stop tracking a request and drop any response that arrives later."""

        with self._cond:
            self._pending.pop(request_id, None)
            self._responses.pop(request_id, None)

    def _describe(self, message: str) -> str:
        """Append the exit code and recent stderr lines to an error message."""

        process = self._process
        code = process.poll() if process is not None else None
        if code is not None:
            message += f" (exit code {code})"
        with self._stderr_lock:
            snapshot = tuple(self._stderr_tail)
        tail = [line for line in snapshot if not line.startswith("[ignored")][-3:]
        if tail:
            message += "; stderr: " + " | ".join(tail)
        return message

    def _request_meta(self, version: str | None) -> dict[str, Any]:
        """Build the per-request ``_meta`` envelope required by modern servers."""

        return {
            f"{_META}protocolVersion": version,
            f"{_META}clientCapabilities": {},
            f"{_META}clientInfo": dict(CLIENT_INFO),
        }

    def _call(self, method: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        """Send a request in the detected era and return its validated result.

        A modern ``-32022`` answer switches to another mutually supported modern
        version and retries, as the versioning spec recommends.
        """

        tried: set[str] = set()
        while True:
            payload = dict(params)
            if self.era is McpEra.MODERN:
                tried.add(str(self.protocol_version))
                payload["_meta"] = self._request_meta(self.protocol_version)
            deadline = time.monotonic() + timeout
            request_id = self._issue(method, payload, deadline)
            try:
                message = self._await(request_id, _remaining(deadline))
            finally:
                self._forget(request_id)
            if message is None:
                reason = f"timeout after {timeout:g}s"
                self._notify("notifications/cancelled", {"requestId": request_id, "reason": reason})
                raise McpTimeoutError(f"MCP server '{self.name}' did not answer {method} within {timeout:g}s")
            error = message.get("error")
            if error is None:
                return _checked_result(method, message.get("result"))
            code, text, data = _error_parts(error)
            if self.era is McpEra.MODERN and code == UNSUPPORTED_PROTOCOL_VERSION:
                supported = _string_list(data.get("supported") if isinstance(data, dict) else None)
                fallback = next((v for v in self._modern_versions if v in supported and v not in tried), None)
                if fallback is not None:
                    self.protocol_version = fallback
                    continue
                raise McpVersionError(
                    f"{method} failed: server supports {supported or 'no listed versions'}, "
                    f"client supports {list(self._modern_versions)}",
                    code=code,
                    data=data,
                )
            raise McpProtocolError(f"{method} failed: {text} (code {code})", code=code, data=data)

    def _negotiate(self, deadline: float, *, allow_legacy: bool) -> None:
        """Detect the server era with a ``server/discover`` probe (stdio dual-era rules)."""

        if not self._modern_versions:
            self._initialize_legacy(deadline, pending_probe=None)
            return
        version = self._modern_versions[0]
        tried: set[str] = set()
        while True:
            tried.add(version)
            probe_id = self._issue("server/discover", {"_meta": self._request_meta(version)}, deadline)
            try:
                response = self._await(probe_id, min(self._probe_timeout, _remaining(deadline)))
            except McpError:
                self._forget(probe_id)
                raise
            if response is None:
                if allow_legacy and self._legacy_versions:
                    self._initialize_legacy(deadline, pending_probe=probe_id)
                    return
                self._forget(probe_id)
                raise McpTimeoutError(f"MCP server '{self.name}' did not answer server/discover")
            self._forget(probe_id)
            error = response.get("error")
            if error is None:
                result = response.get("result")
                if isinstance(result, dict) and isinstance(result.get("supportedVersions"), list):
                    self._adopt_modern(_checked_result("server/discover", result), requested=version)
                    return
                outcome = "a result that is not a DiscoverResult"
            else:
                code, text, data = _error_parts(error)
                if code == UNSUPPORTED_PROTOCOL_VERSION:
                    supported = _string_list(data.get("supported") if isinstance(data, dict) else None)
                    retry = next((v for v in self._modern_versions if v in supported and v not in tried), None)
                    if retry is None:
                        raise McpVersionError(
                            f"MCP server '{self.name}' supports {supported or 'no listed versions'}; "
                            f"client supports {list(self._modern_versions + self._legacy_versions)}",
                            code=code,
                            data=data,
                        )
                    version = retry
                    allow_legacy = False  # a recognized modern error rules out the legacy fallback
                    continue
                if code in _RECOGNIZED_MODERN_ERRORS:
                    raise McpProtocolError(f"server/discover failed: {text} (code {code})", code=code, data=data)
                outcome = f"error {code}: {text}"
            if not (allow_legacy and self._legacy_versions):
                raise McpProtocolError(f"MCP server '{self.name}' is not modern: server/discover got {outcome}")
            self._initialize_legacy(deadline, pending_probe=None)
            return

    def _adopt_modern(self, result: dict[str, Any], *, requested: str) -> None:
        """Record a modern server's identity and pick the protocol version to use."""

        supported = _string_list(result.get("supportedVersions"))
        fallback = next((v for v in self._modern_versions if v in supported), None)
        chosen = requested if requested in supported else fallback
        if chosen is None:
            raise McpVersionError(
                f"MCP server '{self.name}' supports {supported}; client supports {list(self._modern_versions)}"
            )
        meta = result.get("_meta")
        server_info = meta.get(f"{_META}serverInfo") if isinstance(meta, dict) else None
        capabilities = result.get("capabilities")
        instructions = result.get("instructions")
        self.era = McpEra.MODERN
        self.protocol_version = chosen
        self.server_info = server_info if isinstance(server_info, dict) else {}
        self.capabilities = capabilities if isinstance(capabilities, dict) else {}
        self.instructions = instructions if isinstance(instructions, str) else None

    def _initialize_legacy(self, deadline: float, *, pending_probe: int | None) -> None:
        """Run the legacy ``initialize`` handshake (or recover a late modern probe answer)."""

        self._legacy_mode = True
        request_id = self._issue(
            "initialize",
            {"protocolVersion": self._legacy_versions[0], "capabilities": {}, "clientInfo": dict(CLIENT_INFO)},
            deadline,
        )
        try:
            response = self._await(request_id, _remaining(deadline))
        finally:
            self._forget(request_id)
        if response is None:
            if pending_probe is not None:
                self._forget(pending_probe)
            raise McpTimeoutError(
                f"MCP server '{self.name}' answered neither server/discover nor initialize "
                f"within {self._startup_timeout:g}s"
            )
        error = response.get("error")
        if error is not None:
            if pending_probe is not None:
                late = self._await(pending_probe, min(self._probe_timeout, _remaining(deadline)))
                self._forget(pending_probe)
                if late is not None and _is_modern_signal(late):
                    self._legacy_mode = False
                    self._negotiate(deadline, allow_legacy=False)
                    return
            code, text, data = _error_parts(error)
            raise McpProtocolError(f"initialize failed: {text} (code {code})", code=code, data=data)
        if pending_probe is not None:
            self._forget(pending_probe)
        result = _checked_result("initialize", response.get("result"))
        version = result.get("protocolVersion")
        if not isinstance(version, str) or version not in self._legacy_versions:
            raise McpVersionError(
                f"MCP server '{self.name}' negotiated protocol version {version!r}; "
                f"client supports {list(self._legacy_versions)}"
            )
        server_info = result.get("serverInfo")
        capabilities = result.get("capabilities")
        instructions = result.get("instructions")
        self.era = McpEra.LEGACY
        self.protocol_version = version
        self.server_info = server_info if isinstance(server_info, dict) else {}
        self.capabilities = capabilities if isinstance(capabilities, dict) else {}
        self.instructions = instructions if isinstance(instructions, str) else None
        self._notify("notifications/initialized", deadline=max(deadline, time.monotonic() + _NOTIFY_TIMEOUT_SECONDS))


def _remaining(deadline: float) -> float:
    """Return seconds left before ``deadline`` (never negative)."""

    return max(0.0, deadline - time.monotonic())


def _coerce_id(value: Any) -> int | None:
    """Normalize a response id to the integer ids this client issues."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _string_list(value: Any) -> list[str]:
    """Return the string items of a JSON array (empty for anything else)."""

    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _error_parts(error: Any) -> tuple[int | None, str, Any]:
    """Split a JSON-RPC error object into code, message, and data."""

    if not isinstance(error, dict):
        return None, str(error), None
    code = error.get("code")
    valid_code = code if isinstance(code, int) and not isinstance(code, bool) else None
    return valid_code, str(error.get("message", "")), error.get("data")


def _is_modern_signal(message: dict[str, Any]) -> bool:
    """Return whether a probe answer identifies a modern server."""

    result = message.get("result")
    if isinstance(result, dict) and isinstance(result.get("supportedVersions"), list):
        return True
    code, _, _ = _error_parts(message.get("error"))
    return code == UNSUPPORTED_PROTOCOL_VERSION


def _checked_result(method: str, result: Any) -> dict[str, Any]:
    """Validate ``resultType`` (absent means ``complete`` for legacy servers)."""

    if not isinstance(result, dict):
        raise McpProtocolError(f"{method} returned a non-object result")
    result_type = result.get("resultType", "complete")
    if result_type == "complete":
        return result
    if result_type == "input_required":
        raise McpProtocolError(
            f"{method}: the server asked for additional client input (input_required), "
            "which multi-bot-agentic does not provide"
        )
    raise McpProtocolError(f"{method} returned an unrecognized resultType {result_type!r}")


def _parse_tool(item: Any) -> McpToolInfo | None:
    """Convert one ``tools/list`` entry, dropping malformed ones."""

    if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
        return None
    description = item.get("description")
    schema = item.get("inputSchema")
    title = item.get("title")
    annotations = item.get("annotations")
    return McpToolInfo(
        name=item["name"],
        description=description if isinstance(description, str) else "",
        input_schema=schema if isinstance(schema, dict) else {"type": "object"},
        title=title if isinstance(title, str) else None,
        annotations=annotations if isinstance(annotations, dict) else {},
    )


def _write_all(stream: IO[bytes], data: bytes, deadline: float) -> bool:
    """Write ``data`` to the server's non-blocking stdin pipe, giving up at ``deadline``.

    Args:
        stream: Server stdin (non-blocking on POSIX).
        data: Encoded message line.
        deadline: ``time.monotonic()`` value after which a full pipe is abandoned.

    Returns:
        False when the pipe stayed full until the deadline (the line may be partial).
    """

    if sys.platform == "win32":  # anonymous pipes cannot be made non-blocking here; best effort
        stream.write(data)
        stream.flush()
        return True
    fd = stream.fileno()
    view = memoryview(data)
    while view:
        try:
            written = os.write(fd, view)
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)
            continue
        view = view[written:]
    return True


def _close_quietly(stream: IO[bytes] | None) -> None:
    """Close a pipe, ignoring errors from an already-dead peer."""

    if stream is None:
        return
    try:
        stream.close()
    except (OSError, ValueError):
        return


def _group_alive(group: int) -> bool:
    """Return whether any process remains in a POSIX process group."""

    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_tree(process: subprocess.Popen[bytes], group: int | None, *, kill: bool) -> None:
    """Signal the server's whole process group (POSIX) or the process itself (Windows).

    The group is signalled even after the launcher exited, so children that
    outlive it (for example ``npx`` -> ``node``) are still reached.
    """

    try:
        if group is not None and sys.platform != "win32":
            os.killpg(group, signal.SIGKILL if kill else signal.SIGTERM)
        elif process.poll() is None:
            if kill:
                process.kill()
            else:
                process.terminate()
    except OSError:
        return


def _wait_for_tree(process: subprocess.Popen[bytes], group: int | None, timeout: float) -> bool:
    """Wait for the launcher and (on POSIX) every other member of its process group to exit."""

    deadline = time.monotonic() + timeout
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    while group is not None and _group_alive(group):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)
    return True


def _shutdown_process(process: subprocess.Popen[bytes], grace_seconds: float, *, close_stdin: bool = True) -> None:
    """Stop a server per the stdio spec: close stdin, wait, then SIGTERM, then SIGKILL.

    Each step waits for the launcher *and* its whole process group, so a child
    that ignores SIGTERM or survives the launcher is escalated to SIGKILL.
    """

    if close_stdin:
        _close_quietly(process.stdin)
    group = process.pid if sys.platform != "win32" else None
    for kill in (None, False, True):
        if kill is not None:
            _signal_tree(process, group, kill=kill)
        if _wait_for_tree(process, group, grace_seconds):
            return
