# 01_ARCHITECTURE.md

## Purpose

This document describes the major runtime components of LASI and how they interact.

It does not define schemas, prompts, database tables, or implementation details. Those belong in separate documents.

---

## Architectural Principle

LASI separates execution, reasoning, memory, knowledge, reporting, and governance.

No single subsystem is authoritative over everything.

The database records what happened.
MLflow stores experimental artifacts.
The knowledge layer stores what was learned.
The scientist provider gives recommendations.
The decision system authorizes actions.
OpenCode commands, agents, and skills are the operating surface. Reusable Python services are the implementation layer behind that surface.

The current implementation is partial. `services/` provides typed contracts, configuration, dataset, experiment, tool, decision, provider, report, remote, knowledge, memory, and outcome components, with unit and fixture integration tests. These are reusable service building blocks, not proof that every OpenCode command and workflow step is wired end to end.

OpenCode skill identifiers are canonical only in their hyphenated form, for example `dataset-intake`, `dataset-characterization`, and `decision-review`. All skill procedures, contracts, checklists, and examples are discovered from and maintained under `.opencode/skills/`; no secondary skill tree is supported.

---

## High-Level System Diagram

```text
OpenCode admin command
│
LASI Administrator ── durable assignment state / pause / resume / cancel
│
ProjectRunner ── lease / wakeup / checkpoint / repeated coordinator invocation
│
Internal OpenCode coordinator / specialist agent / skill
│
Reusable Python Services
│
├── Tool Registry
├── Component Registry and Graph Runner
├── Experiment Planner
├── SSH Remote Runner
├── Scientist Provider
├── Decision System
├── Report Generator
├── Knowledge Curator
│
├── Database
│   └── Operational Memory
│
├── MLflow
│   └── Experiment Artifacts
│
└── Knowledge Layer
    └── Semantic Memory

The administrator is active only for a user lifecycle operation. The runner is active only while an assignment is runnable or awaiting a timed wakeup. The coordinator is inside this loop: each invocation reconstructs minimum-sufficient context from durable state, performs one bounded research turn, and emits a typed next-action directive. Finishing a coordinator response does not finish the assignment. This control loop does not change subsystem ownership, approval, provenance, or governance boundaries.

In the normal OpenCode UI, `lasi-coordinator` remains a subagent and `lasi-admin` remains the only primary LASI agent. Because non-interactive `opencode run --agent` selects primary agents, the runner supplies an inline child-process-only configuration that promotes `lasi-coordinator` for that invocation. The override is not written to user configuration and does not expose a second interactive LASI surface.

## Nested ICM Context Architecture

LASI uses a nested, selective context hierarchy above its machine-native state:

```text
Structured memory (SQL, graph/vector retrieval, telemetry, MLflow)
                         ↓
System ICM (institutional semantic context)
                         ↓
Project ICM (isolated project semantic context)
                         ↓
Agent/action context (ephemeral minimum-sufficient context)
                         ↓
Model or tool
```

ICM is a durable human- and LLM-readable semantic layer. It does not replace the
database, artifact store, knowledge registry, telemetry, queues, or experiment
tracking. `services.context.ICMStore` owns explicit system and project artifacts;
`ContextResolver` selects only relevant documents for an action. Existing
workflow services remain responsible for orchestration, authorization, and
structured persistence.

Detailed context contracts and lifecycle rules are defined in
`15_CONTEXT_SYSTEM.md`.

## Component Execution Layer

The tool registry remains the execution allowlist used by decisions. The
component registry is the typed reusable-implementation catalog behind an
approved `component_pipeline` tool run. Components are explicitly registered
with a Pydantic configuration schema, semantic version, input/output artifact
ports, modality/problem compatibility, resource metadata, lifecycle state, and
known limitations. They are never dynamically imported from a configuration.

The component graph runner validates and resolves a specification before it can
execute, then records one normal `ToolRunResult` per component. It can execute
trusted local components in process today; remote worker and isolation backends
remain behind the existing execution contracts. Generated or third-party code
is not a registry component until it has passed a governed promotion process.
`ComponentPromotionService` requires source-experiment evidence, test,
dependency-review, and code-review references plus an explicit `update_toolbox`
approval; proposal data never contains an import path or executable code.

When the coordinator needs a novel implementation during a research loop, it
creates a typed `ComponentRequest` for the independent component reviewer. The
reviewer inspects immutable source, dependencies, contracts, tests, resource
bounds, side effects, and containment. `ComponentReviewService` may
automatically authorize the implementation only as an `experimental` component
in a registry scoped to that project. Correctable stability gaps route back to
the builder. Security, containment, privacy, trust, or systemic stability risks
escalate to a human. Project-local authorization never implies shared toolbox
promotion, which retains its existing governed approval path.

Project ICM is organized into task, context, work, evidence, and output areas.
Experiments may add isolated subdirectories under project work. Agents should
communicate through declared artifact contracts and evidence records rather than
transcript or scratchpad injection.

## Token Usage Telemetry

Every durable workflow action has an append-only operational-memory metering
entry. LLM/provider actions record exact token counts and billed USD only when
the provider or agent runtime returns an authoritative receipt. LASI never
derives usage from prompt text, estimates it with an LLM, or computes a price
from a model-price table. Non-token actions are explicitly `not_applicable`;
missing provider receipts are explicitly `not_available`. Per-project and
cross-project summaries expose measured tokens, billed cost, metering coverage,
and action-type breakdowns for waste and improvement analysis.
