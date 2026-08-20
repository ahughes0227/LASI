"""MCP boundary for external systems.

Local components remain ordinary Python calls.  MCP exists for the boundary where LASI
talks to something outside itself, and an MCP tool is not a special kind of tool: it is
registered with a `ToolSpec`, executed through the tool runner, and gated by the decision
system exactly like any other executable boundary.

The point of this module is that there is no second path.
"""

from .adapter import (
    MCP_BACKEND,
    McpClient,
    McpToolAdapter,
    McpToolDescriptor,
    McpUnavailableError,
    register_mcp_tool,
    tool_spec_from_descriptor,
)

__all__ = [
    "MCP_BACKEND",
    "McpClient",
    "McpToolAdapter",
    "McpToolDescriptor",
    "McpUnavailableError",
    "register_mcp_tool",
    "tool_spec_from_descriptor",
]
