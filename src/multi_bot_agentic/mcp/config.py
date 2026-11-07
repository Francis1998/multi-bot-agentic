"""Claude-Desktop-compatible MCP server configuration with per-server safety options.

The file format is the ``mcpServers`` JSON used by Claude Desktop, Claude Code,
Cursor, and most MCP clients::

    {"mcpServers": {"notes": {"command": "python3", "args": ["notes_server.py"], "env": {}}}}

Each server entry may also carry multi-bot-agentic safety options
(``allowedTools``, ``deniedTools``, ``callTimeoutSeconds``,
``startupTimeoutSeconds``, ``maxResultBytes``, ``redactResults``, ``disabled``)
and an optional ``cwd``. Other clients ignore these keys, so one file can be
shared. Only stdio servers are supported; remote (``url``) entries are skipped
with a warning.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

_SERVER_NAME = re.compile(r"^[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*$")
_MAX_SERVER_NAME_CHARS = 64
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

# Mirrors the official MCP Python SDK: servers inherit only these variables unless
# the config passes more through ``env``, so provider API keys never leak by default.
_POSIX_INHERITED_ENV = ("HOME", "LOGNAME", "PATH", "SHELL", "TERM", "USER")
_WINDOWS_INHERITED_ENV = (
    "APPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "USERNAME",
    "USERPROFILE",
)
INHERITED_ENV_VARS: tuple[str, ...] = _WINDOWS_INHERITED_ENV if sys.platform == "win32" else _POSIX_INHERITED_ENV

DEFAULT_CALL_TIMEOUT_SECONDS = 30.0
DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESULT_BYTES = 16_384

_STDIO_KEYS = frozenset({"command", "args", "env", "cwd", "type"})
_SAFETY_KEYS = frozenset(
    {
        "allowedTools",
        "deniedTools",
        "callTimeoutSeconds",
        "startupTimeoutSeconds",
        "maxResultBytes",
        "redactResults",
        "disabled",
    }
)


class McpConfigError(ValueError):
    """Raised when an MCP config file is missing, malformed, or unsafe."""


@dataclass(frozen=True)
class McpServerConfig:
    """One stdio MCP server plus the safety options applied to its tools.

    Attributes:
        name: Config key; becomes the ``mcp__<name>__`` tool-name namespace.
        command: Executable to launch.
        args: Command-line arguments.
        env: Extra environment variables (placeholders already expanded).
        cwd: Working directory for the server process (``None`` inherits).
        allowed_tools: Glob patterns of server tool names to expose (``None`` = all).
        denied_tools: Glob patterns of server tool names to hide (wins over allow).
        call_timeout_seconds: Per ``tools/call`` timeout.
        startup_timeout_seconds: Budget for launch plus protocol-era detection.
        max_result_bytes: UTF-8 byte cap applied to each tool result text.
        redact_results: Scrub emails/phones/tokens from results before logging.
        disabled: Skip this server without removing it from the file.
    """

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: Path | None = None
    allowed_tools: tuple[str, ...] | None = None
    denied_tools: tuple[str, ...] = ()
    call_timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS
    startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS
    max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES
    redact_results: bool = False
    disabled: bool = False

    def exposes(self, tool_name: str) -> bool:
        """Return whether the allow/deny lists expose a server tool.

        Args:
            tool_name: Tool name as reported by the server.

        Returns:
            True when the tool passes ``allowedTools`` and is not in ``deniedTools``.
        """

        if any(fnmatchcase(tool_name, pattern) for pattern in self.denied_tools):
            return False
        if self.allowed_tools is None:
            return True
        return any(fnmatchcase(tool_name, pattern) for pattern in self.allowed_tools)

    def process_env(self, environ: Mapping[str, str] | None = None) -> dict[str, str]:
        """Build the least-privilege environment for the server process.

        Args:
            environ: Parent environment (defaults to ``os.environ``).

        Returns:
            Allowlisted inherited variables overlaid with the configured ``env``.
        """

        source = os.environ if environ is None else environ
        merged = {key: source[key] for key in INHERITED_ENV_VARS if key in source}
        merged.update(self.env)
        return merged


@dataclass(frozen=True)
class McpConfig:
    """Parsed MCP configuration file.

    Attributes:
        servers: Server entries in file order (including disabled ones).
        source: File the config was loaded from, if any.
        warnings: Non-fatal issues such as unknown keys or skipped remote servers.
    """

    servers: tuple[McpServerConfig, ...]
    source: Path | None = None
    warnings: tuple[str, ...] = ()

    @property
    def enabled_servers(self) -> tuple[McpServerConfig, ...]:
        """Return servers that are not ``disabled``."""

        return tuple(server for server in self.servers if not server.disabled)


def load_mcp_config(path: Path, environ: Mapping[str, str] | None = None) -> McpConfig:
    """Load and validate an MCP config file.

    Args:
        path: JSON file in ``mcpServers`` format.
        environ: Environment used for ``${VAR}`` expansion (defaults to ``os.environ``).

    Returns:
        Parsed configuration.

    Raises:
        McpConfigError: If the file cannot be read or fails validation.
    """

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise McpConfigError(f"cannot read MCP config {path}: {error.strerror or error}") from error
    except UnicodeDecodeError as error:
        raise McpConfigError(f"MCP config {path} is not UTF-8 text: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise McpConfigError(f"MCP config {path} is not valid JSON: {error.msg} (line {error.lineno})") from error
    return parse_mcp_config(data, base_dir=path.resolve().parent, environ=environ, source=path)


def parse_mcp_config(
    data: Any,
    *,
    base_dir: Path,
    environ: Mapping[str, str] | None = None,
    source: Path | None = None,
) -> McpConfig:
    """Validate decoded MCP config JSON.

    Args:
        data: Decoded JSON document.
        base_dir: Directory used to resolve a relative ``cwd``.
        environ: Environment used for ``${VAR}`` expansion (defaults to ``os.environ``).
        source: Optional file path recorded on the result.

    Returns:
        Parsed configuration.

    Raises:
        McpConfigError: If the document fails validation.
    """

    env_source = os.environ if environ is None else environ
    if not isinstance(data, dict):
        raise McpConfigError("MCP config must be a JSON object with an 'mcpServers' object")
    entries = data.get("mcpServers", data.get("servers"))
    if not isinstance(entries, dict):
        raise McpConfigError("MCP config must contain an 'mcpServers' object")

    servers: list[McpServerConfig] = []
    warnings: list[str] = []
    for name, entry in entries.items():
        if len(name) > _MAX_SERVER_NAME_CHARS or not _SERVER_NAME.match(name):
            raise McpConfigError(
                f"invalid MCP server name {name!r}: use letters and digits separated by single '-' or '_' "
                f"(max {_MAX_SERVER_NAME_CHARS} chars) so tool names stay collision-free"
            )
        if not isinstance(entry, dict):
            raise McpConfigError(f"MCP server '{name}' must be a JSON object")
        server_type = entry.get("type", "stdio")
        if "url" in entry or server_type != "stdio":
            warnings.append(f"MCP server '{name}': only stdio servers are supported; skipping type={server_type!r}")
            continue
        unknown = sorted(set(entry) - _STDIO_KEYS - _SAFETY_KEYS)
        if unknown:
            warnings.append(f"MCP server '{name}': ignoring unknown key(s): {', '.join(unknown)}")
        servers.append(_parse_server(name, entry, base_dir=base_dir, environ=env_source))
    return McpConfig(servers=tuple(servers), source=source, warnings=tuple(warnings))


def _parse_server(name: str, entry: dict[str, Any], *, base_dir: Path, environ: Mapping[str, str]) -> McpServerConfig:
    """Validate one server entry.

    Args:
        name: Server name.
        entry: Raw server entry.
        base_dir: Directory used to resolve a relative ``cwd``.
        environ: Environment used for placeholder expansion.

    Returns:
        Parsed server config.

    Raises:
        McpConfigError: If a field has the wrong type or value.
    """

    def expand(value: str, field_name: str) -> str:
        def substitute(match: re.Match[str]) -> str:
            variable, default = match.group(1), match.group(2)
            if variable in environ:
                return environ[variable]
            if default is not None:
                return default
            raise McpConfigError(f"MCP server '{name}': environment variable {variable} is not set ({field_name})")

        return _PLACEHOLDER.sub(substitute, value)

    command = entry.get("command")
    if not isinstance(command, str) or not command.strip():
        raise McpConfigError(f"MCP server '{name}': 'command' must be a non-empty string")
    args = entry.get("args", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise McpConfigError(f"MCP server '{name}': 'args' must be a list of strings")
    env = entry.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(val, str) for val in env.values()):
        raise McpConfigError(f"MCP server '{name}': 'env' must map strings to strings")
    cwd_value = entry.get("cwd")
    if cwd_value is not None and (not isinstance(cwd_value, str) or not cwd_value.strip()):
        raise McpConfigError(f"MCP server '{name}': 'cwd' must be a non-empty string")
    cwd = None if cwd_value is None else base_dir / Path(expand(cwd_value, "cwd")).expanduser()

    return McpServerConfig(
        name=name,
        command=expand(command, "command"),
        args=tuple(expand(item, "args") for item in args),
        env={key: expand(val, f"env.{key}") for key, val in env.items()},
        cwd=cwd,
        allowed_tools=_patterns(name, entry, "allowedTools") if "allowedTools" in entry else None,
        denied_tools=_patterns(name, entry, "deniedTools") if "deniedTools" in entry else (),
        call_timeout_seconds=_positive_number(name, entry, "callTimeoutSeconds", DEFAULT_CALL_TIMEOUT_SECONDS),
        startup_timeout_seconds=_positive_number(name, entry, "startupTimeoutSeconds", DEFAULT_STARTUP_TIMEOUT_SECONDS),
        max_result_bytes=int(_positive_number(name, entry, "maxResultBytes", DEFAULT_MAX_RESULT_BYTES, integer=True)),
        redact_results=_flag(name, entry, "redactResults"),
        disabled=_flag(name, entry, "disabled"),
    )


def _patterns(name: str, entry: dict[str, Any], key: str) -> tuple[str, ...]:
    """Validate an allow/deny list of glob patterns."""

    value = entry[key]
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise McpConfigError(f"MCP server '{name}': '{key}' must be a list of non-empty strings")
    return tuple(value)


def _positive_number(name: str, entry: dict[str, Any], key: str, default: float, *, integer: bool = False) -> float:
    """Validate an optional finite positive number (``bool``, NaN, and infinity are rejected)."""

    value = entry.get(key, default)
    valid_type = isinstance(value, int) if integer else isinstance(value, (int, float))
    if isinstance(value, bool) or not valid_type or not math.isfinite(value) or value <= 0:
        kind = "positive integer" if integer else "positive number"
        raise McpConfigError(f"MCP server '{name}': '{key}' must be a {kind}")
    return float(value)


def _flag(name: str, entry: dict[str, Any], key: str) -> bool:
    """Validate an optional boolean flag."""

    value = entry.get(key, False)
    if not isinstance(value, bool):
        raise McpConfigError(f"MCP server '{name}': '{key}' must be true or false")
    return value
