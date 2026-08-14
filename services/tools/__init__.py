"""Bounded tool registration and local execution services."""

from .adapters import characterize_dataset, validate_dataset
from .builtins import (
    register_builtin_tools,
    register_direct_horizon_gbdt,
    register_seasonal_naive_baseline,
    register_tabular_baseline,
)
from .errors import ToolError, ToolNotFoundError, ToolVersionError
from .registry import RegisteredTool, ToolRegistry
from .runner import LocalToolRunner, ToolContext, ToolOutput

__all__ = [
    "LocalToolRunner",
    "RegisteredTool",
    "ToolContext",
    "ToolError",
    "ToolNotFoundError",
    "ToolOutput",
    "ToolRegistry",
    "ToolVersionError",
    "characterize_dataset",
    "register_builtin_tools",
    "register_direct_horizon_gbdt",
    "register_seasonal_naive_baseline",
    "register_tabular_baseline",
    "validate_dataset",
]
