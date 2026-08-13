"""Local-only persistence boundary for remote operational records."""

from collections.abc import Iterator
from copy import deepcopy
from typing import Protocol

from .models import RemoteRunRecord


class RemoteRunStore(Protocol):
    """The local harness owns this store; transports never write to it."""

    def save(self, record: RemoteRunRecord) -> None: ...

    def get(self, remote_run_id: str) -> RemoteRunRecord: ...


class InMemoryRemoteRunStore:
    """Small deterministic store for tests and service composition."""

    def __init__(self) -> None:
        self._records: dict[str, RemoteRunRecord] = {}

    def save(self, record: RemoteRunRecord) -> None:
        self._records[record.remote_run_id] = deepcopy(record)

    def get(self, remote_run_id: str) -> RemoteRunRecord:
        return deepcopy(self._records[remote_run_id])

    def all(self) -> Iterator[RemoteRunRecord]:
        return iter(deepcopy(list(self._records.values())))
