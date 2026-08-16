# 01_ARCHITECTURE.md

## Workflow Control Plane

Installed workflows are governed JSON packages under `_workflows/<workflow_id>/workflow.json`.
Pydantic contracts in `services.contracts` are canonical; `_schemas/workflow.schema.json`
is a derived interoperability schema. Versioned prompts, reasoning rubrics, and agent
profiles live under `system/` and are resolved by `WorkflowLoader`. OpenCode skills
remain procedural guidance and discovery metadata, not workflow authority.

The workflow compiler selects eligible nodes and emits a planning-only `TaskGraphProposal`.
SQLite runtime state remains authoritative for leases, task readiness, persisted plans,
allowing decisions, results, and explicit blocked/failed/optional states.

Workflow packages are authored through the governed workflow-development pipeline:
`WorkflowDefinition` → REUSE/COMPOSE/EXTEND/NEW resolution → `WorkflowBuildPlan` →
fixed package shell → validation → `WorkflowRegistrationProposal`. This is the
template for adding future workflows; hand-authored graph formats are not supported.

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

Capability development is a governed side path into this architecture. It may
produce validated semantic capability packages and registration proposals, but
it cannot bypass the component/tool registries or the decision and approval
boundaries that control executable behavior.

The current implementation is partial. `services/` provides typed contracts, configuration, dataset, experiment, tool, decision, provider, report, remote, knowledge, memory, and outcome components, with unit and fixture integration tests. These are reusable service building blocks, not proof that every OpenCode command and workflow step is wired end to end.

OpenCode skill identifiers are canonical only in their hyphenated form, for example `dataset-intake`, `dataset-characterization`, and `decision-review`. All skill procedures, contracts, checklists, and examples are discovered from and maintained under `.opencode/skills/`; no secondary skill tree is supported.

---

## High-Level System Diagram

```text
OpenCode admin command
│
LASI Administrator ── durable assignment state / pause / resume / cancel
│
Semantic Task Runtime ── validate / persist / lease / ingest / checkpoint
│
Planning-only Coordinator ── TaskGraphProposal JSON
│
SQLite Task DAG ── ready tasks / dependencies / attempts / events / usage
│
Specialist and Critic Agents ── AgentTask in / AgentResult out
│
Reusable Python Services
│
├── Tool Registry
├── Component Registry and Graph Runner
├── Capability Registry, Resolver, Builder, and Registrar
├── Planner Catalog Graph and Traversal
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

In the normal OpenCode UI, `lasi-coordinator` remains a subagent and `lasi-admin`
remains the only primary research-lifecycle agent. The separate
`lasi-capability-builder` primary agent is reachable only through the governed
capability-development command. Because non-interactive `opencode run --agent`
selects primary agents, the runner supplies an inline child-process-only
configuration that promotes `lasi-coordinator` for that invocation. The
override is not written to user configuration and does not expose a second
interactive research surface.

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

## Capability Development Layer

LASI expands its action space through a typed compiler pipeline: natural-language
intent becomes `CapabilitySpec`, structural resolution chooses REUSE, COMPOSE,
EXTEND, or NEW, research is limited to the recorded gap, and a frozen
`CapabilityBuildPlan` controls work inside a fixed package shell. Validation
must pass before the registrar can create a proposal. Shared registration
requires an explicit `update_toolbox` approval bound to the package hash.

The semantic capability registry answers what LASI can do. The component catalog
answers what reusable implementation machinery exists. The tool registry still
constrains execution. See `16_CAPABILITY_DEVELOPMENT_SYSTEM.md`.

The planner catalog is a rebuildable SQLite projection of approved registry
metadata. It contains typed workflow, workflow-node, capability, and component
nodes plus relationships such as `uses_capability`, `requires_component`,
`implements_capability`, `depends_on_capability`, and `contains_node`. The
planner may use lexical or future vector retrieval to find candidates, then
must traverse and validate typed contracts before producing an
`ExperimentPlan`. The catalog never authorizes execution and is not the
epistemic knowledge graph.

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

## Research Control Plane

Every autonomous assignment owns a SQLite-backed task graph and versioned
task-graph proposals. `RuntimeTaskRecord` and dependency rows are the executable
interpretation of the agenda. Markdown plans and handoff notes are readable
projections, not competing authority. The runtime rejects stale graphs, cycles,
unknown rubrics, missing dependencies, and plan-backed tasks without persisted
allowing decisions.

Research-loop state is persisted alongside the agenda. Meaningful improvement
routes to evidence review or error analysis before further implementation.
Capability maturity is explicit in `ToolSpec`; only `production_ready` tools can
generate executable evidence.

The semantic task runtime is the current control spine. A stateless,
planning-only orchestrator returns `TaskGraphProposal`; the runtime stores task
DAGs, dependencies, attempts, leases, context snapshots, rubric evaluations,
events, duration, artifacts, and usage receipts in SQLite. Specialists receive
`AgentTask` and return `AgentResult`. They never write operational SQL directly.

Versioned reasoning rubrics have two purposes: guide a capability's reasoning
procedure and define the minimum evidence needed to accept its result. The
runtime verifies deterministic and evidentiary criteria; subjective scientific
claims are continuously challenged by an independent critic. Scientific
checkpoints automatically create critic tasks, and material unresolved
criticisms route to the cheapest discriminating falsification plan.

ICM remains the nested task/context/work/evidence/output structure, but it is a
generated context view rather than workflow authority. SQLite supplies working
and episodic memory, runtime code supplies procedural memory, governed Markdown
supplies semantic memory, typed nodes/edges supply associative retrieval, and
MLflow/artifact storage preserves produced evidence.

Every durable workflow action has an append-only operational-memory metering
entry. LLM/provider actions record exact token counts and billed USD only when
the provider or agent runtime returns an authoritative receipt. LASI never
derives usage from prompt text, estimates it with an LLM, or computes a price
from a model-price table. Non-token actions are explicitly `not_applicable`;
missing provider receipts are explicitly `not_available`. Per-project and
cross-project summaries expose measured tokens, billed cost, metering coverage,
and action-type breakdowns for waste and improvement analysis.
