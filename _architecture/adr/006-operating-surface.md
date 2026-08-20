# ADR-006: Operating surface — OpenCode vs. Python CLI

**Status:** open

## Context

Today OpenCode is the only supported operating surface. Seven administrator
commands drive assignment lifecycle; a detached worker leases tasks from the SQL
runtime and invokes `opencode run` for agent work. `01_ARCHITECTURE.md` states
this plainly, and `services/runtime/opencode_cli.py` preflights the binary before
assignment state changes.

External guidance assumed a Python CLI (`uv run lassie solve …`) as the entry
point. That is not a cosmetic difference: it determines where the assignment
lifecycle lives, and whether end-to-end tests can run without an `opencode`
binary on `PATH`.

This ADR is deliberately left open. No current workstream depends on the answer,
and deciding it prematurely would be guessing.

## Options

1. **OpenCode stays canonical.** Any new runtime work happens inside a leased
   task. Preserves the existing control plane and the governed command surface.
2. **Python CLI becomes canonical.** OpenCode becomes one client among several.
   Requires re-homing the administrator and detached-worker lifecycle.
3. **Both, CLI as a thin client** over the same services. More surface to keep
   honest, but end-to-end tests and demos stop depending on an external binary.

## Criteria for deciding

- Can the full end-to-end suite run with no `opencode` binary present? This is
  currently a real constraint on test coverage.
- Does the detached-worker lifecycle survive the change intact?
- Does it multiply the number of ways to start work? Two entry points that can
  both mutate assignment state is a governance problem, not a convenience.

## Consequences of leaving it open

Acceptable for now, but it should be settled before the surface calcifies
further. Every additional command written against one surface raises the cost of
choosing the other.
