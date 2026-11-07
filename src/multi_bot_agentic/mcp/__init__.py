"""Model Context Protocol (MCP) tool bridge.

Start stdio MCP servers from a Claude-Desktop-style ``mcpServers`` config and
use their tools as ordinary ``ToolAdapter`` objects named ``mcp__<server>__<tool>``.
"""

from multi_bot_agentic.mcp.bridge import (
    McpArgumentError,
    McpServerStatus,
    McpToolAdapter,
    McpToolset,
    coerce_arguments,
    namespaced_tool_name,
)
from multi_bot_agentic.mcp.client import (
    LEGACY_PROTOCOL_VERSIONS,
    MODERN_PROTOCOL_VERSIONS,
    McpCallResult,
    McpEra,
    McpError,
    McpProtocolError,
    McpTimeoutError,
    McpToolInfo,
    McpTransportError,
    McpVersionError,
    StdioMcpClient,
)
from multi_bot_agentic.mcp.config import McpConfig, McpConfigError, McpServerConfig, load_mcp_config

__all__ = [
    "LEGACY_PROTOCOL_VERSIONS",
    "MODERN_PROTOCOL_VERSIONS",
    "McpArgumentError",
    "McpCallResult",
    "McpConfig",
    "McpConfigError",
    "McpEra",
    "McpError",
    "McpProtocolError",
    "McpServerConfig",
    "McpServerStatus",
    "McpTimeoutError",
    "McpToolAdapter",
    "McpToolInfo",
    "McpToolset",
    "McpTransportError",
    "McpVersionError",
    "StdioMcpClient",
    "coerce_arguments",
    "load_mcp_config",
    "namespaced_tool_name",
]
