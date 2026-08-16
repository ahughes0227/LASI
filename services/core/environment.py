"""Allowlisted child process environments.

A child process inherits nothing by default.  The parent environment of a LASI
run holds operator credentials, cloud tokens, and shell state that agent turns
and registered component commands have no business reading, so each child gets
an environment assembled from a named allowlist plus the variables the caller
sets explicitly.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

# Variables any child needs to run at all: process lookup, home, locale, and
# temporary storage.
_BASE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PATH",
        "SHELL",
        "TMPDIR",
        "TZ",
        "USER",
    }
)

# OpenCode agent turns: harness markers, OpenCode's own configuration, and the
# model provider credentials the turn is expected to use.
AGENT_ENVIRONMENT_ALLOWLIST: frozenset[str] = _BASE_ALLOWLIST | frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "LASI_OPENCODE_EXECUTABLE",
        "OPENCODE_CONFIG",
        "OPENCODE_CONFIG_CONTENT",
        "OPENCODE_DISABLE_AUTOUPDATE",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
)

# Registered component commands: an interpreter environment, no credentials.
COMPONENT_ENVIRONMENT_ALLOWLIST: frozenset[str] = _BASE_ALLOWLIST | frozenset(
    {
        "PYTHONHASHSEED",
        "PYTHONPATH",
        "VIRTUAL_ENV",
    }
)

# Operator escape hatch for a deployment that needs another variable (a proxy, a
# second provider).  It is read from the parent environment, never from agent
# output, and cannot be used to smuggle in the allowlist mechanism itself.
PASSTHROUGH_VARIABLE = "LASI_CHILD_ENV_PASSTHROUGH"


def build_child_environment(
    allowlist: Iterable[str],
    *,
    overrides: Mapping[str, str] | None = None,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a child environment from `allowlist` plus explicit `overrides`."""
    parent = os.environ if source is None else source
    names = set(allowlist) | _passthrough_names(parent)
    environment = {name: parent[name] for name in sorted(names) if name in parent}
    environment.update(overrides or {})
    return environment


def _passthrough_names(parent: Mapping[str, str]) -> set[str]:
    raw = parent.get(PASSTHROUGH_VARIABLE, "")
    names = {item.strip() for item in raw.split(",")}
    return {name for name in names if name and name != PASSTHROUGH_VARIABLE}


__all__ = [
    "AGENT_ENVIRONMENT_ALLOWLIST",
    "COMPONENT_ENVIRONMENT_ALLOWLIST",
    "PASSTHROUGH_VARIABLE",
    "build_child_environment",
]
