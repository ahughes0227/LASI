"""Errors raised by the tool boundary."""


class ToolError(Exception):
    """Base error for registry and execution failures."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not registered."""


class ToolVersionError(ToolError):
    """Raised when a requested tool version is incompatible."""
