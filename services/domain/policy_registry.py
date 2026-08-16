"""Safe discovery and validation of YAML domain policies."""

from pathlib import Path

import yaml

from .policy_models import DomainPolicy


class DomainPolicyRegistry:
    def __init__(self, root: Path):
        self._policies = self._load(root)

    @classmethod
    def from_items(cls, policies: list[DomainPolicy]) -> "DomainPolicyRegistry":
        registry = cls.__new__(cls)
        registry._policies = registry._validate_unique(policies)
        return registry

    def all(self, include_drafts: bool = False) -> tuple[DomainPolicy, ...]:
        statuses = {"approved", "retired"}
        if include_drafts:
            statuses.add("draft")
        return tuple(
            policy
            for policy in self._sorted()
            if policy.status in statuses and (include_drafts or policy.status != "retired")
        )

    def for_action(self, action: str) -> tuple[DomainPolicy, ...]:
        return tuple(
            policy
            for policy in self._sorted()
            if policy.status == "approved" and policy.action == action
        )

    def _sorted(self) -> list[DomainPolicy]:
        return sorted(self._policies, key=lambda policy: (-policy.priority, policy.policy_id))

    @classmethod
    def _load(cls, root: Path) -> list[DomainPolicy]:
        policies: list[DomainPolicy] = []
        for path in sorted(root.rglob("*.yaml")):
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            policies.append(DomainPolicy.model_validate(value))
        return cls._validate_unique(policies)

    @staticmethod
    def _validate_unique(policies: list[DomainPolicy]) -> list[DomainPolicy]:
        seen: set[tuple[str, str]] = set()
        for policy in policies:
            key = (policy.policy_id, policy.version)
            if key in seen:
                raise ValueError(
                    f"duplicate domain policy version: {policy.policy_id!r} {policy.version!r}"
                )
            seen.add(key)
        return list(policies)
