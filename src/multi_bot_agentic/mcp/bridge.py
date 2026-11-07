"""Expose MCP server tools as multi-bot-agentic ``ToolAdapter`` objects.

Mirrors how OpenAI Agents SDK (``MCPServerStdio``), smolagents
(``ToolCollection.from_mcp``), PydanticAI, CrewAI (``MCPServerAdapter``) and
LangGraph (``langchain-mcp-adapters``) consume MCP servers: every tool a
configured server exposes becomes a namespaced ``mcp__<server>__<tool>``
adapter. Because the adapters implement the ordinary ``ToolAdapter`` protocol,
the runner's safety allowlist, bot scoping, rate limiting, redaction, and the
durable event log apply to them unchanged.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from multi_bot_agentic.mcp.client import (
    McpCallResult,
    McpError,
    McpProtocolError,
    McpTimeoutError,
    McpToolInfo,
    StdioMcpClient,
)
from multi_bot_agentic.mcp.config import McpConfig, McpServerConfig
from multi_bot_agentic.models import ToolInvocation, ToolResult, ToolSpec
from multi_bot_agentic.observation_redactor import ObservationRedactor

TOOL_NAME_PREFIX = "mcp__"
# MCP tool-name guidance (1-128 chars of A-Z a-z 0-9 _ - .); anything else could
# break the ``TOOL:<name>:<payload>`` directive, so such tools are skipped.
_REMOTE_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_MAX_DESCRIPTION_CHARS = 400


class McpArgumentError(ValueError):
    """Raised when a ``TOOL:`` payload cannot be mapped onto a tool's input schema."""


def namespaced_tool_name(server_name: str, tool_name: str) -> str:
    """Return the collision-free registry name for an MCP tool.

    Server names cannot contain ``__`` (see ``McpServerConfig``), so the first
    ``__`` after the prefix always separates the server from the tool.

    Args:
        server_name: Config key of the server.
        tool_name: Tool name reported by the server.

    Returns:
        Name such as ``mcp__notes__search_notes``.
    """

    return f"{TOOL_NAME_PREFIX}{server_name}__{tool_name}"


def coerce_arguments(arguments: Mapping[str, Any], input_schema: Mapping[str, Any]) -> dict[str, Any]:
    """Map runner tool arguments onto an MCP tool's JSON arguments.

    The decision engine passes ``{"text": <payload>}`` from ``TOOL:<name>:<payload>``.
    A payload that is a JSON object is used as the arguments; plain text fills the
    tool's single required (or only) property, decoding JSON scalars for
    non-string properties. Structured mappings from library callers pass through.

    Args:
        arguments: Invocation arguments.
        input_schema: Tool ``inputSchema``.

    Returns:
        Arguments for ``tools/call``.

    Raises:
        McpArgumentError: If the payload is ambiguous, malformed, or misses required keys.
    """

    signature = ToolSpec(name="", description="", input_schema=dict(input_schema)).signature() or "no arguments"
    properties = input_schema.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    raw_required = input_schema.get("required")
    required = [key for key in raw_required if isinstance(key, str)] if isinstance(raw_required, list) else []

    if set(arguments) - {"text"}:
        result = dict(arguments)
    else:
        raw = arguments.get("text", "")
        text = (raw if isinstance(raw, str) else json.dumps(raw)).strip()
        if text.startswith("{"):
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as error:
                message = f"arguments look like JSON but are invalid ({error.msg}); expected {signature}"
                raise McpArgumentError(message) from error
            if not isinstance(decoded, dict):
                raise McpArgumentError(f"arguments must be a JSON object; expected {signature}")
            result = decoded
        elif not properties:
            result = {}
        else:
            target = required[0] if len(required) == 1 else (next(iter(properties)) if len(properties) == 1 else None)
            if target is None:
                raise McpArgumentError(f"pass a JSON object of arguments; expected {signature}")
            result = {target: _coerce_scalar(target, text, properties.get(target))}

    missing = [key for key in required if key not in result]
    if missing:
        raise McpArgumentError(f"missing required argument(s): {', '.join(missing)}; expected {signature}")
    return result


def _coerce_scalar(name: str, text: str, schema: Any) -> Any:
    """Convert plain text for one property, decoding JSON for non-string types."""

    declared = schema.get("type") if isinstance(schema, dict) else None
    if isinstance(declared, list):
        types = {item for item in declared if isinstance(item, str)}
    else:
        types = {declared} if isinstance(declared, str) else set()
    if not types or "string" in types:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise McpArgumentError(f"argument '{name}' expects {declared}; got {text!r}") from error


def render_content(result: McpCallResult) -> str:
    """Render MCP content blocks as observation text.

    Text blocks are kept verbatim; binary blocks are summarized, so base64
    payloads never reach the model or the event log. ``structuredContent`` is
    serialized only when the server sent no content blocks.

    Args:
        result: Tool call result.

    Returns:
        Human-readable result text.
    """

    parts: list[str] = []
    for block in result.content:
        kind = block.get("type")
        if kind == "text":
            parts.append(str(block.get("text", "")))
        elif kind in ("image", "audio"):  # tuple: a malformed unhashable "type" must not raise
            data = block.get("data")
            size = len(data) if isinstance(data, str) else 0
            parts.append(f"[{kind} {block.get('mimeType', 'unknown')}: {size} base64 chars omitted]")
        elif kind == "resource_link":
            parts.append(f"[resource_link {block.get('name') or block.get('uri')}: {block.get('uri')}]")
        elif kind == "resource":
            resource = block.get("resource")
            resource = resource if isinstance(resource, dict) else {}
            text = resource.get("text")
            parts.append(text if isinstance(text, str) else f"[resource {resource.get('uri')}: binary omitted]")
        else:
            parts.append(f"[{kind} content omitted]")
    if not parts and result.structured_content is not None:
        return json.dumps(result.structured_content, sort_keys=True, ensure_ascii=False)
    return "\n".join(parts)


def truncate_utf8(text: str, max_bytes: int) -> tuple[str, int]:
    """Cap ``text`` at ``max_bytes`` UTF-8 bytes without splitting a character.

    Args:
        text: Result text.
        max_bytes: Byte budget for the kept text (the marker is appended on top).

    Returns:
        The possibly truncated text and the original byte length.
    """

    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, len(encoded)
    kept = encoded[:max_bytes].decode("utf-8", errors="ignore")
    marker = f"\n…[truncated: kept {len(kept.encode('utf-8'))} of {len(encoded)} bytes; raise maxResultBytes]"
    return kept + marker, len(encoded)


def _summarize(description: str, fallback: str) -> str:
    """Collapse whitespace and bound a tool description for prompts and listings."""

    collapsed = " ".join(description.split()) or fallback
    if len(collapsed) <= _MAX_DESCRIPTION_CHARS:
        return collapsed
    return collapsed[: _MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"


class McpToolAdapter:
    """``ToolAdapter`` that forwards one MCP tool through its server's shared client.

    Failures follow the repository's tool-failure semantics: they never raise,
    they return ``ToolResult(ok=False)`` so the model can self-correct.
    ``isError`` results, JSON-RPC errors, timeouts, and dead servers are told
    apart by ``metadata["error_kind"]``.
    """

    def __init__(self, *, server: McpServerConfig, tool: McpToolInfo, client: StdioMcpClient) -> None:
        """Wrap a tool.

        Args:
            server: Server config (timeouts, result cap, redaction).
            tool: Tool definition from ``tools/list``.
            client: Started client for the server.
        """

        self.name = namespaced_tool_name(server.name, tool.name)
        self.description = f"[MCP {server.name}] {_summarize(tool.description, tool.title or tool.name)}"
        self.server_name = server.name
        self.remote_name = tool.name
        self.input_schema = dict(tool.input_schema)
        self._server = server
        self._client = client
        self._redactor = ObservationRedactor() if server.redact_results else None

    def spec(self) -> ToolSpec:
        """Return the model-facing catalog entry for this tool."""

        return ToolSpec(name=self.name, description=self.description, input_schema=self.input_schema)

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Call the MCP tool.

        Args:
            invocation: Runner invocation (``{"text": payload}`` or structured arguments).

        Returns:
            Tool result; ``ok`` is False for argument, protocol, timeout, transport,
            and ``isError`` failures.
        """

        metadata: dict[str, Any] = {"mcp_server": self.server_name, "mcp_tool": self.remote_name}
        try:
            arguments = coerce_arguments(invocation.arguments, self.input_schema)
        except McpArgumentError as error:
            return self._result(False, str(error), metadata, error_kind="invalid_arguments")
        metadata["mcp_arguments"] = arguments
        started = time.monotonic()
        try:
            result = self._client.call_tool(
                self.remote_name, arguments, timeout_seconds=self._server.call_timeout_seconds
            )
        except McpTimeoutError as error:
            return self._result(False, str(error), self._timed(metadata, started), error_kind="timeout")
        except McpProtocolError as error:
            metadata["error_code"] = error.code
            return self._result(False, str(error), self._timed(metadata, started), error_kind="protocol_error")
        except McpError as error:
            return self._result(False, str(error), self._timed(metadata, started), error_kind="transport_error")
        metadata = self._timed(metadata, started)
        metadata["content_types"] = [str(block.get("type")) for block in result.content]
        error_kind = "tool_error" if result.is_error else None
        return self._result(not result.is_error, render_content(result), metadata, error_kind=error_kind)

    def _timed(self, metadata: dict[str, Any], started: float) -> dict[str, Any]:
        """Add era, protocol version, and latency to result metadata."""

        era = self._client.era
        return {
            **metadata,
            "mcp_era": era.value if era is not None else None,
            "mcp_protocol_version": self._client.protocol_version,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }

    def _result(self, ok: bool, text: str, metadata: dict[str, Any], *, error_kind: str | None) -> ToolResult:
        """Redact and truncate result text, then build the ``ToolResult``."""

        final = dict(metadata)
        if error_kind is not None:
            final["error_kind"] = error_kind
        if self._redactor is not None:
            redaction = self._redactor.redact(text)
            text = redaction.redacted_text
            final["redactions"] = redaction.redaction_count
        text, original_bytes = truncate_utf8(text, self._server.max_result_bytes)
        final["result_bytes"] = original_bytes
        final["truncated"] = original_bytes > self._server.max_result_bytes
        return ToolResult(tool_name=self.name, ok=ok, content=text, metadata=final)


@dataclass(frozen=True)
class McpServerStatus:
    """Startup outcome for one configured server.

    Attributes:
        name: Server config key.
        era: ``modern`` or ``legacy`` once detected.
        protocol_version: Negotiated protocol version.
        server_info: Self-reported ``serverInfo`` (display only, never trusted).
        tools: Exposed namespaced tool names.
        hidden_tools: Server tool names hidden by ``allowedTools``/``deniedTools``.
        skipped_tools: Tool names skipped because they are invalid or duplicated.
        error: Startup error, when the server could not be used.
        disabled: True when the config marks the server ``disabled``.
    """

    name: str
    era: str | None = None
    protocol_version: str | None = None
    server_info: Mapping[str, Any] | None = None
    tools: tuple[str, ...] = ()
    hidden_tools: tuple[str, ...] = ()
    skipped_tools: tuple[str, ...] = ()
    error: str | None = None
    disabled: bool = False


ClientFactory = Callable[[McpServerConfig], StdioMcpClient]


def default_client_factory(server: McpServerConfig) -> StdioMcpClient:
    """Build a least-privilege stdio client for a configured server.

    Args:
        server: Server config.

    Returns:
        Unstarted client.
    """

    return StdioMcpClient(
        (server.command, *server.args),
        name=server.name,
        env=server.process_env(),
        cwd=server.cwd,
        startup_timeout_seconds=server.startup_timeout_seconds,
    )


class McpToolset:
    """Start configured MCP servers and expose their tools as ``ToolAdapter`` objects.

    Use as a context manager (or call :meth:`close`) so every server process
    tree is terminated when the run ends.
    """

    def __init__(self, config: McpConfig, *, client_factory: ClientFactory = default_client_factory) -> None:
        """Prepare (but do not start) the toolset.

        Args:
            config: Parsed MCP config.
            client_factory: Builds a client per server (injectable for tests).
        """

        self._config = config
        self._client_factory = client_factory
        self._clients: list[StdioMcpClient] = []
        self._tools: dict[str, McpToolAdapter] = {}
        self._statuses: tuple[McpServerStatus, ...] | None = None

    def __enter__(self) -> McpToolset:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def tools(self) -> dict[str, McpToolAdapter]:
        """Return exposed adapters keyed by namespaced tool name (server order)."""

        return dict(self._tools)

    @property
    def statuses(self) -> tuple[McpServerStatus, ...]:
        """Return per-server startup outcomes (empty before :meth:`start`)."""

        return self._statuses or ()

    @property
    def failed(self) -> tuple[McpServerStatus, ...]:
        """Return servers that could not be started or listed."""

        return tuple(status for status in self.statuses if status.error is not None)

    def specs(self) -> tuple[ToolSpec, ...]:
        """Return catalog entries for every exposed tool."""

        return tuple(adapter.spec() for adapter in self._tools.values())

    def start(self) -> tuple[McpServerStatus, ...]:
        """Start every enabled server, list its tools, and apply allow/deny lists.

        A server that fails to start is recorded in :attr:`failed` instead of
        raising, so callers decide whether to continue.

        Returns:
            Per-server startup outcomes in config order.
        """

        if self._statuses is not None:
            return self._statuses
        statuses: list[McpServerStatus] = []
        for server in self._config.servers:
            if server.disabled:
                statuses.append(McpServerStatus(name=server.name, disabled=True))
                continue
            client = self._client_factory(server)
            try:
                client.start()
                infos = client.list_tools(timeout_seconds=server.call_timeout_seconds)
            except McpError as error:
                client.close()
                statuses.append(McpServerStatus(name=server.name, error=str(error)))
                continue
            except BaseException:
                client.close()
                raise
            self._clients.append(client)
            statuses.append(self._register(server, client, infos))
        self._statuses = tuple(statuses)
        return self._statuses

    def close(self) -> None:
        """Terminate every started server."""

        while self._clients:
            self._clients.pop().close()

    def _register(self, server: McpServerConfig, client: StdioMcpClient, infos: list[McpToolInfo]) -> McpServerStatus:
        """Wrap a server's exposed tools and summarize what was filtered."""

        exposed: list[str] = []
        hidden: list[str] = []
        skipped: list[str] = []
        for info in infos:
            if not _REMOTE_TOOL_NAME.match(info.name):
                skipped.append(info.name)
                continue
            if not server.exposes(info.name):
                hidden.append(info.name)
                continue
            adapter = McpToolAdapter(server=server, tool=info, client=client)
            if adapter.name in self._tools:
                skipped.append(info.name)
                continue
            self._tools[adapter.name] = adapter
            exposed.append(adapter.name)
        era = client.era
        return McpServerStatus(
            name=server.name,
            era=era.value if era is not None else None,
            protocol_version=client.protocol_version,
            server_info=dict(client.server_info),
            tools=tuple(exposed),
            hidden_tools=tuple(hidden),
            skipped_tools=tuple(skipped),
        )
