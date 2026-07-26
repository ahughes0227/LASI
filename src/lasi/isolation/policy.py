from __future__ import annotations

# fmt: off

from dataclasses import dataclass

# ruff: noqa: E501, I001


@dataclass(frozen=True)
class IsolationProfile:
    profile_id: str
    version: str = "1"
    network: str = "deny_all"
    subprocess: str = "deny"
    external_provider: str = "deny"
    allowed_read_paths: tuple[str, ...] = ()
    allowed_write_paths: tuple[str, ...] = ()
    benchmark_read_only: bool = True


@dataclass(frozen=True)
class IsolationCheck:
    category: str
    passed: bool
    observed: str
    expected: str


def benchmark_default() -> IsolationProfile:
    return IsolationProfile(profile_id="benchmark-default")


def preflight(profile: IsolationProfile, *, enforcement_backend: str = "process-policy") -> list[IsolationCheck]:
    """Application preflight; callers must use an OS sandbox for hostile code."""
    return [
        IsolationCheck("network", profile.network == "deny_all", profile.network, "deny_all"),
        IsolationCheck("subprocess", profile.subprocess == "deny", profile.subprocess, "deny"),
        IsolationCheck("provider", profile.external_provider == "deny", profile.external_provider, "deny"),
        IsolationCheck("backend", bool(enforcement_backend), enforcement_backend, "non-empty"),
    ]


class BenchmarkIsolationError(PermissionError):
    """Raised when a protected benchmark lacks verified containment."""


def require_benchmark_isolation(parameters: dict[str, object]) -> list[IsolationCheck]:
    if not parameters.get("benchmark_protected", False):
        return []
    profile = parameters.get("isolation_profile")
    if not isinstance(profile, IsolationProfile):
        raise BenchmarkIsolationError("protected benchmark requires an isolation profile")
    checks = preflight(profile, enforcement_backend=str(parameters.get("isolation_backend", "")))
    if not all(check.passed for check in checks):
        raise BenchmarkIsolationError("benchmark isolation preflight failed")
    if not profile.benchmark_read_only:
        raise BenchmarkIsolationError("benchmark workspace must be read-only")
    return checks
