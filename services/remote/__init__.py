"""Controlled SSH-shaped execution using testable local transports.

Real SSH is intentionally not implemented in this wave.  The transport boundary
keeps the runner auditable and makes it possible to add an approved backend later
without changing the ToolRunResult contract.
"""

from .models import (
    CleanupResult,
    EnvironmentCheck,
    RemoteRunRecord,
    RemoteRunState,
    TransportResult,
)
from .persistence import InMemoryRemoteRunStore, RemoteRunStore
from .runner import DEFAULT_REMOTE_TIMEOUT_SECONDS, RemoteRunner
from .transports import LoopbackTransport, MockTransport, RemoteTransport

__all__ = [
    "CleanupResult",
    "DEFAULT_REMOTE_TIMEOUT_SECONDS",
    "EnvironmentCheck",
    "InMemoryRemoteRunStore",
    "LoopbackTransport",
    "MockTransport",
    "RemoteRunRecord",
    "RemoteRunState",
    "RemoteRunStore",
    "RemoteRunner",
    "RemoteTransport",
    "TransportResult",
]
