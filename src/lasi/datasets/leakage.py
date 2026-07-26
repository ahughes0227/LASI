from __future__ import annotations

# fmt: off

from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any

# ruff: noqa: E501, I001


@dataclass(frozen=True)
class LeakageFinding:
    rule_id: str
    severity: str
    message: str
    columns: tuple[str, ...] = ()


@dataclass
class LeakageAudit:
    findings: list[LeakageFinding] = field(default_factory=list)
    status: str = "passed"

    @property
    def blocking(self) -> bool:
        return any(finding.severity == "block" for finding in self.findings)


def audit_tabular(train: list[dict[str, Any]], test: list[dict[str, Any]], *,
                  target_columns: Sequence[str], identifier_columns: Sequence[str] = (),
                  group_columns: Sequence[str] = (), time_columns: Sequence[str] = ()) -> LeakageAudit:
    audit = LeakageAudit()
    train_columns = set(train[0]) if train else set()
    test_columns = set(test[0]) if test else set()
    leaked_targets = sorted(set(target_columns) & test_columns)
    if leaked_targets:
        audit.findings.append(LeakageFinding("target_in_test", "block", "target column appears in test", tuple(leaked_targets)))
    if train and test:
        feature_names = sorted((train_columns & test_columns) - set(identifier_columns))
        train_keys = {tuple(row.get(name) for name in feature_names) for row in train}
        test_keys = {tuple(row.get(name) for name in feature_names) for row in test}
        if train_keys & test_keys:
            audit.findings.append(LeakageFinding("duplicate_train_test", "block", "exact feature rows overlap train and test"))
    suspicious = [name for name in train_columns if any(token in name.lower() for token in ("label", "target", "outcome", "score", "prediction")) and name not in target_columns]
    if suspicious:
        audit.findings.append(LeakageFinding("suspicious_column", "review", "column name suggests post-outcome data", tuple(sorted(suspicious))))
    if not group_columns:
        audit.findings.append(LeakageFinding("group_configuration_missing", "review", "group leakage could not be assessed"))
    if not time_columns:
        audit.findings.append(LeakageFinding("time_configuration_missing", "review", "temporal leakage could not be assessed"))
    audit.status = "blocked" if audit.blocking else ("review_required" if audit.findings else "passed")
    return audit
