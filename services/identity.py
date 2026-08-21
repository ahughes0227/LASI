"""Authoritative in-process identity graph boundary."""

from __future__ import annotations

from collections import defaultdict

from .contracts import IdentityGrant, IdentitySnapshot


class IdentityGraph:
    def __init__(self, *, policy_version: str) -> None:
        self.policy_version = policy_version
        self._grants: dict[str, list[IdentityGrant]] = defaultdict(list)
        self._roles: dict[str, set[str]] = defaultdict(set)

    def add_grant(self, grant: IdentityGrant) -> None:
        if grant in self._grants[grant.subject_id]:
            raise ValueError("duplicate identity grant")
        self._grants[grant.subject_id].append(grant)

    def add_role(self, subject_id: str, role: str) -> None:
        self._roles[subject_id].add(role)

    def snapshot(self, subject_id: str) -> IdentitySnapshot:
        return IdentitySnapshot(
            actor_id=subject_id,
            roles=frozenset(self._roles[subject_id]),
            grants=tuple(self._grants[subject_id]),
            policy_version=self.policy_version,
        )
