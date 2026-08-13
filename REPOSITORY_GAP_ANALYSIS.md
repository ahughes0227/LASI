# LASI Repository Gap Analysis

## Purpose

This document compares the current LASI repository with the architecture described in `AGENTS.md`, `_architecture/`, `_core/`, `_workflows/`, `_schemas/`, and `_templates/`. OpenCode agents, commands, and skills under `.opencode/` are the supported operating surface.

The assessment is limited to repository structure and implementation readiness for agent-first AI model development and experimentation. It does not propose changing LASI's authority boundaries, and it does not implement or reorganize anything.

## Executive Assessment

LASI is currently a strong **architecture, governance, agent-procedure scaffold, and early executable service package**. It is not yet a complete end-to-end AI engineering workspace.

The repository already describes the intended operating model unusually well:

- Evidence is separated from interpretation, recommendation, authorization, and institutional knowledge.
- Scientist providers recommend but do not execute.
- Experiments require plans and decisions before execution.
- Datasets are intended to be framework-neutral, versioned assets.
- Reports are fixed, structured artifacts rather than unconstrained model prose.
- Outcomes and failures are treated as evidence.
- High-consequence actions require human approval.

The principal gap is integration and enforcement across the existing service components. The repository now has typed contracts, persistence, dataset and experiment services, tool execution, decision gates, provider normalization, report rendering, remote execution, knowledge retrieval, outcomes, and tests. OpenCode procedures and `_workflows/**` still do not form a general workflow runner, and several service boundaries remain partial or in-memory.

In practical terms, a general-purpose agent can use OpenCode procedures and invoke reusable service components for bounded operations, but the repository cannot yet guarantee one fully routed, persisted, resumable, end-to-end workflow for every documented path.

## Current Repository State

| Area | Current state | Readiness |
|---|---|---|
| Architecture | Fifteen subsystem documents in `_architecture/` | Strong conceptual foundation |
| Agent policy | Detailed operating rules in `AGENTS.md` and `_core/authority_boundaries.md` | Strong procedural foundation |
| OpenCode surface | Nine commands, specialist agents, and hyphenated skills under `.opencode/` | Present; bounded routing/procedure surface |
| Workflows | Five workflow definitions with ordered `STEP.md` files | Declarative; no general workflow runner |
| Skills | Canonical hyphenated OpenCode skills under `.opencode/skills/`, including their contracts, checklists, and examples | Procedures with partial service integration |
| Contracts | Pydantic models in `services/contracts/` plus five YAML schemas | Typed runtime contracts; YAML alignment remains incomplete |
| Templates | Markdown templates for major artifacts | Manual scaffolding |
| Knowledge | Correct category structure with README placeholders | Empty semantic-memory scaffold |
| Tickets | Filesystem lifecycle folders with README placeholders | Empty manual queue scaffold |
| Projects | README describing a project folder convention | No project instances |
| Tools | Registry, built-in tools, adapters, and runner in `services/tools/` | Early local execution surface; coverage is narrow |
| Application code | `services/` service package plus persisted diagnostic workflow | MVP vertical slice implemented; broader workflows remain |
| Operational memory | SQLAlchemy models, SQLite setup, Alembic migration, repositories | MVP persistence present; broader records/integration remain |
| Tests | Unit tests plus durable diagnostic workflow and Wave 5b integration tests | Present; broader workflow coverage remains |
| CI and developer tooling | `pyproject.toml` and `.github/workflows/ci.yml` define checks | Present; MLflow emits upstream filesystem warnings |
| Git repository | Git repository with existing worktree | Available; knowledge review process remains procedural |

## What Is Already Aligned

### 1. Authority boundaries are explicit

The repository consistently preserves the distinction between:

```text
what happened
what was produced
what was learned
what is recommended
what is authorized
```

This is the most important architectural requirement for agent-first operation. The intended ownership model is clear across `AGENTS.md`, `_architecture/01_ARCHITECTURE.md`, `_architecture/05_MEMORY_SYSTEM.md`, `_architecture/08_DECISION_SYSTEM.md`, and `_architecture/14_GOVERNANCE.md`.

### 2. Agent procedures are modular

The `.opencode/skills/` and `_workflows/` trees provide bounded procedures for dataset intake, characterization, experiment planning, remote execution, scientist review, decision review, reporting, outcome recording, knowledge curation, and workflow authoring.

This is a good foundation for agent-first work because tasks are decomposed into explicit inputs, expected outputs, stopping conditions, and handoffs instead of relying on a single unconstrained agent prompt.

### 3. The target research lifecycle is coherent

The intended path from dataset intake through outcome recording is understandable and preserves review gates. The dataset diagnostic workflow already identifies the correct major phases:

```text
intake
validation
characterization
experiment planning
execution
scientist review
decision review
reporting
outcome recording
```

### 4. The repository is designed around evidence rather than metric chasing

The architecture supports baseline probes, learning curves, error analysis, cluster analysis, partial successes, structured failures, stop decisions, and production outcomes. This is well aligned with an AI engineering workspace intended to diagnose performance limits rather than behave as a generic AutoML system.

### 5. The MVP scope is appropriately restrained

The documentation generally favors SQLite, MLflow, static HTML, SSH, deterministic gates, a mock provider, and rule-based retrieval before more complex systems. That bias is suitable for building a reliable vertical slice before adding scheduling, vector databases, dashboards, or foundation-model training.

## Critical Gaps

### 1. Partial executable service spine

The target architecture names OpenCode commands, agents, and skills over a reusable Python service layer. That layer now exists in `services/`, including contracts/configuration, dataset validation and characterization, plan compilation, tools, decisions, providers, reports, remote execution, knowledge retrieval, memory, and outcomes. The MVP service spine is implemented in `services.workflows.diagnostic`; broader documented workflows still require their own orchestration.

The authoritative MVP code path now performs the minimum end-to-end sequence:

```text
load project configuration
validate a dataset manifest
create a dataset version record
characterize the dataset
compile an experiment plan
evaluate a decision gate
run an approved tool
record metrics and artifacts
create a diagnostic packet
obtain a normalized scientist review
record a decision
render a static report
record the project outcome
```

The remaining gap is broader workflow coverage and resumability beyond this tested vertical slice.

### 2. Reusable service package is early, not complete

The implementation follows the expected `services/` directory structure directly. The service package is present and tested, but broader project-lifecycle orchestration and complete OpenCode integration remain incremental work.

Missing structural areas include:

```text
services/core/
services/configs/
services/datasets/
services/experiments/
services/tools/
services/providers/
services/decisions/
services/memory/
services/knowledge/
services/reports/
services/remote/
services/governance/
tests/
```

The underscore-prefixed directories hold architecture, schema, template, and workflow specifications; they do not contain agent or skill definitions. Canonical skills are under `.opencode/skills/` with hyphenated identifiers.

### 3. Incomplete OpenCode-to-service integration

`AGENTS.md` and `_architecture/01_ARCHITECTURE.md` define OpenCode commands, agents, and skills as the operating surface. The repository now has reusable implementations behind many bounded operations, but commands remain procedure prompts rather than a general service API or workflow runner.

At minimum, the target design implies OpenCode procedures for project creation/status, dataset validation and characterization, experiment planning and execution, decision review, provider review, report generation, outcome updates, and SSH diagnostics. The procedures exist in part under `.opencode/`, but the service calls and runtime authorization layer do not.

This means OpenCode agents have a documented operating surface and a growing service boundary, but not yet a stable command-to-service route for every workflow step. Direct file manipulation remains possible for procedures that lack integration, so this is still a governance and reliability risk.

### 4. Contracts are incomplete and not executable

Only five schemas exist:

- `_schemas/dataset_manifest.schema.yaml`
- `_schemas/experiment_plan.schema.yaml`
- `_schemas/scientist_review.schema.yaml`
- `_schemas/decision_record.schema.yaml`
- `_schemas/static_report.schema.yaml`

Important architecture contracts have no schema or typed model:

- `ProjectConfig`
- `DatasetVersion`
- `DatasetCharacterization`
- `DatasetImprovementProposal`
- `ToolSpec`
- `ToolRunResult`
- `RemoteRunSpec`
- `RemoteHostProfile`
- `DiagnosticPacket`
- `ProviderProfile`
- `ProviderError`
- `ProjectOutcome`
- `OutcomeEvent`
- `KnowledgeDocument`
- `KnowledgeProposal`
- `ApprovalRecord`
- `ArtifactRecord`
- `EvaluationPolicy`

The repository now has a typed contract package, schema generation and validation
helpers, schema versioning, and contract tests. Authored YAML remains a stable
handoff representation rather than a generated copy of the Pydantic schema.

### 5. Contract artifacts and remaining drift

The principal contract-artifact mismatches in the authored schemas, templates, and
examples have been corrected against `services/contracts/models.py`.

Specific inconsistencies include:

- The authored YAML schemas are not mechanically generated or checked against Pydantic JSON Schema; field additions can still drift until a conformance check covers them.
- Markdown templates and examples are not parsed and validated automatically against their corresponding contracts.
- Workflow and OpenCode procedure references are outside this correction ownership; any remaining legacy wording there must be handled by the coordinator-owned workflow/OpenCode change.
- `ProjectOutcome` and `OutcomeEvent` are separate frozen contracts; the current outcome template documents the current outcome record, while event-example conformance remains a test/documentation gap.

Agent-first execution depends on strict machine-readable handoffs. The remaining
drift is therefore enforcement and automated conformance coverage, not an
intentional alternate contract in the owned authored artifacts.

### 6. Narrow tool registry and executable tools

The architecture assigns the tool registry responsibility for constraining what can run. `services/tools/` now provides `ToolSpec`, a registry, built-in tool registrations, adapters, and a runner. The current built-ins are intentionally narrow and several planned experiment tools remain pass-through or unimplemented.

Missing pieces include:

- A `ToolSpec` contract
- Tool discovery and registration
- Tool versions and approval status
- Input and output validation
- Supported modalities and problem types
- Supported execution backends
- Expected artifact definitions
- Failure and partial-success behavior
- A local tool runner
- Initial characterization, baseline, error-analysis, and report tools

The registry enables bounded local execution for its supported tools, but coverage, persistent run registration, MLflow linkage, and complete OpenCode invocation are still gaps.

### 7. Partial operational memory

SQLite is the MVP source of operational truth, and `services/memory/` plus Alembic now provide database setup, models, migration support, and repository behavior for the implemented records.

Durable coverage is not yet uniform across projects, dataset versions, characterizations, experiment plans, tool runs, remote runs, scientist reviews, decisions, approvals, reports, outcomes, artifacts, recommendation results, and tool usefulness. Some records remain contract-only or use in-memory stores.

The filesystem ticket folders are not a substitute for operational memory because they provide no transactional state, referential integrity, query layer, event history, or enforcement of valid transitions.

### 8. Partial artifact memory and MLflow integration

MLflow is a declared dependency, local tracking URI convention is implemented by `MlflowArtifactStore`, and the durable diagnostic workflow records tool and report artifacts with provenance. Advanced artifact resolution and remote persistence remain outside this MVP slice.

As a result, LASI cannot currently preserve or connect models, metrics, plots, predictions, embeddings, environment snapshots, provider responses, reports, or remote logs to their provenance records.

### 9. Early dataset system implementation

`services/datasets/service.py` now validates manifests, reads the supported fixture format, computes hashes, creates dataset-version contracts, and produces characterization results. Canonical storage policy, full lineage persistence, comparability enforcement, benchmark protection, and broad runtime adapters remain incomplete.

The manifest schema is also too minimal for the first documented point-cloud use case. It defines a generic file list but not a sample-level contract with IDs, labels, point-cloud references, metadata, and splits.

The repository therefore cannot yet guarantee the central rule that every result is tied to an identified, validated, comparable dataset version.

### 10. Early experiment planning and execution implementation

`services/experiments/` now provides deterministic plan compilation, execution-decision checks, duplicate detection, reproducibility records, and diagnostics helpers. Full local execution orchestration, result/artifact persistence, diagnostic-packet assembly, and workflow-state integration remain incomplete.

Workflow manifests identify phases but have no workflow engine to parse dependencies, validate preconditions, persist state, resume work, enforce approval points, or route handoffs.

### 11. Governance is documented but not enforced

The decision and governance documents clearly define risk levels, approval requirements, proposal conversion, policy checks, overrides, and exceptions. No implementation enforces these rules.

Approval flags in workflow files and templates are currently documentary. An agent can bypass them because there is no gate between a plan and execution, no approval record store, no policy evaluator, and no command authorization layer.

For an agent-first workspace, unenforced governance is a major gap: written safety boundaries are useful guidance but do not create runtime control.

### 12. Scientist-provider abstraction is present, integration is partial

`services/providers/` now provides provider contracts, profiles, privacy handling, normalization, artifact recording helpers, errors, and a deterministic mock provider. Provider invocation from a complete workflow, durable review registration, and all privacy/provenance paths remain to be integrated.

The required deterministic mock provider is also absent. This blocks provider-independent tests of review, decision, report, and failure workflows.

### 13. Static report renderer is present, registration is incomplete

The target report is fixed static HTML generated from typed `StaticReportData`. `services/reports/` now validates and renders through a fixed Jinja template and refuses overwrite, with report tests. Artifact registration, all provenance resolution, and golden coverage for every missing-state variant remain gaps.

Missing pieces include:

- A canonical report-data model
- A fixed HTML template and CSS
- Consistent rendering of missing and blocked sections
- Artifact resolution
- Provenance links
- Privacy-aware sample display
- Immutable report registration
- Golden report fixtures

The current Markdown outline is useful as a design artifact but does not satisfy the static-report requirement.

### 14. Remote execution is implemented with test transports, SSH integration remains bounded

`services/remote/` now provides remote models, a runner, persistence protocols, mock/loopback transports, environment checks, staging, command execution, logs, artifact retrieval, and cleanup behavior. A production SSH transport and a dedicated `doctor-ssh` service operation are not yet complete, and OpenCode routing remains procedural.

The absence of this layer means the workspace is not yet set up for agents to use larger CPU/GPU environments while retaining local authority and provenance.

### 15. Knowledge structure exists but contains no governed knowledge

The `knowledge/` tree correctly separates facts, policies, hypotheses, lessons, literature, toolbox notes, taxonomies, and templates. Each area currently contains only a README.

There are no front-matter-bearing knowledge documents, metadata validator, retrieval service, proposal registry, status enforcement, Git commit references, or tests for retrieval priority and contradictory knowledge.

The workspace is a Git repository, so Git-backed semantic memory has repository history and identity available. Knowledge review, proposal approval, and recording the resulting commit reference remain procedural rather than enforced by the service layer.

### 16. Outcome ledger is present, integration is incomplete

`ProjectOutcome` and `OutcomeEvent` contracts plus `OutcomeService` provide status-transition validation and append-style persistence behavior. Full project lifecycle integration and OpenCode-backed operation remain incomplete.

This prevents LASI from distinguishing validation-only success from production success in operational memory, despite that distinction being one of the system's core design goals.

### 17. Tests and fixtures exist; CI and end-to-end breadth remain gaps

`tests/` now covers contracts, configuration, datasets, tools, decisions, experiments, providers, reports, remote execution, knowledge, outcomes, persistence, the Wave 5b fixture, and the durable diagnostic workflow. Workflow/skill conformance and broader end-to-end paths remain outside the MVP vertical slice.

The existing schema/example drift demonstrates why this matters. A contract conformance test would already catch several current inconsistencies.

Missing quality foundations include:

- Unit and service tests
- Schema and example conformance tests
- Workflow and `STEP.md` linting
- Mock-provider tests
- Loopback or mocked SSH tests
- Golden report tests
- Database migration tests
- Static analysis and formatting
- CI workflows
- Dependency and security checks

### 18. Reproducible development setup is defined, bootstrap remains light

`pyproject.toml` now defines the package, dependencies, Python version, test paths, Ruff, and mypy settings. A lockfile, environment example, secrets guidance, task runner, container option, and bootstrap command remain absent.

An agent cannot reliably determine how to install, test, lint, or run LASI. This is a direct agent-first usability gap because every agent would have to infer or recreate the development environment.

### 19. Narrow end-to-end reference project

There are synthetic artifact examples, but no small project demonstrates the intended vertical slice with a real or fixture dataset.

A reference project is needed to prove that all contracts join correctly across dataset version, plan, decision, tool run, artifacts, scientist review, report, and outcome. Without it, subsystem documents can remain individually plausible while integration gaps go undetected.

## Agent-First Development Gaps

The repository has good instructions for agents, but agent-first development requires more than agent-readable Markdown.

### Stable machine interfaces are missing

Agents need stable OpenCode procedures and typed inputs rather than permission to manipulate internal files directly. The OpenCode surface, reusable service layer, schemas, and tool registry should form the bounded operating interface.

### State transitions are not enforced

An agent can create artifacts out of order because lifecycle prerequisites exist only in prose. There is no state machine preventing execution before validation, approval, or plan creation.

### Idempotency and resumability are undefined

There is no mechanism for an agent to determine whether a step is already complete, safely retry a failed step, resume after interruption, or avoid duplicating an equivalent experiment.

### Handoffs are not validated

Skills identify expected outputs, but no runtime checks that an output exists, matches its schema, references valid provenance, or satisfies the next step's preconditions.

### Context loading is manual

Agents must inspect many documents to reconstruct current project state. There is no project-state summary, diagnostic packet builder, bounded knowledge retriever, or command that returns the authoritative context for the next action.

### Permissions are advisory

The authority model is strong in prose but there is no technical boundary preventing agents from modifying datasets, knowledge, policies, or outcome status directly.

### Observability is absent

There is no structured logging, trace ID convention, event log, run status command, health check, or audit query interface. Agents cannot reliably diagnose where a workflow failed or what evidence was persisted.

### No evaluation of the agents themselves

The repository does not yet define conformance or quality tests for agent outputs, such as schema adherence, evidence-reference validity, unsupported-claim detection, decision-gate compliance, or recommendation usefulness over time.

## Documentation Gaps and Open Decisions

The architecture is broad, but several decisions must be resolved before implementation can be unambiguous.

### Canonical schema strategy

It is unclear whether YAML files are intended to be JSON Schema, descriptive YAML contracts, or generated representations of typed Python models. A single canonical source is needed to prevent drift among code, schemas, templates, examples, and reports.

### Project configuration contract

The repository repeatedly references project configuration, evaluation policy, budget, privacy mode, provider profile, and remote host profile, but no unified `ProjectConfig` contract defines how they are selected and versioned.

### Dataset format for the MVP

`_architecture/03_DATASET_SYSTEM.md` intentionally leaves the point-cloud canonical representation unsettled. Implementation cannot begin cleanly until one primary format and sample-level manifest contract are selected.

### Workflow execution semantics

Workflow manifests do not define dependency syntax, artifact bindings, state persistence, retries, idempotency keys, timeout behavior, conditional steps, or versioning. These semantics should be specified before building a workflow runner.

### Taxonomy ownership

Controlled values are repeated across architecture files and schemas but do not always agree. There is no canonical taxonomy source from which schemas, code enums, documentation, and reports are generated or checked.

### Artifact URI and identifier conventions

The architecture requires stable IDs and cross-store provenance, but there is no documented format for IDs, artifact URIs, workspace paths, MLflow references, Git references, or content hashes.

### Approval representation

The documents describe decision records, approval records, and proposal records, but the relationships and lifecycle among them are not fully specified. In particular, approval conditions, expiration, implementation confirmation, and human identity are not represented consistently in current schemas.

### Repository-level onboarding

There is no root README explaining the current maturity, intended audience, supported workflow, repository map, setup path, or distinction between the specification scaffold and future runtime package.

## Gap Priority

| Priority | Gap | Why it blocks progress |
|---|---|---|
| P0 | Canonical typed contracts and taxonomy alignment | Every service and agent handoff depends on them |
| P0 | Reusable service package, configuration, and OpenCode integration | Establishes the supported operating surface |
| P0 | SQLite operational memory and provenance IDs | Creates the local source of truth |
| P0 | Tool registry, local runner, and deterministic decision gate | Makes bounded execution possible |
| P0 | One end-to-end fixture project | Proves subsystem integration |
| P1 | Dataset validation, versioning, and characterization | Establishes trustworthy experimental inputs |
| P1 | Experiment planner and structured result handling | Turns questions into reproducible evidence |
| P1 | MLflow artifact adapter | Preserves produced artifacts and links them to records |
| P1 | Mock scientist provider and normalization | Enables provider-independent workflow testing |
| P1 | Static HTML report renderer | Produces the required human review artifact |
| P1 | Outcome event ledger | Completes the project lifecycle |
| P1 | Automated tests and CI | Prevents contract and behavior drift |
| P2 | SSH remote backend | Enables controlled use of remote compute |
| P2 | Rule-based knowledge retrieval and proposals | Activates semantic memory without overbuilding |
| P2 | Workflow resumability and richer observability | Makes longer agent runs reliable |
| P3 | Sabbatical automation and foundation opportunity scoring | Requires accumulated operational history first |

## Recommended Implementation Sequence

This sequence is a recommendation for later work, not a change made by this assessment.

1. Reconcile the five existing schemas with architecture documents, templates, examples, and shared taxonomies.
2. Add the missing MVP contracts as typed models with generated or validated schemas.
3. Establish the reusable service package, configuration loader, OpenCode integration, test harness, and CI baseline.
4. Implement SQLite operational memory, stable identifiers, migrations, and artifact-reference records.
5. Implement project creation and lifecycle-state services.
6. Implement one canonical dataset format, sample-level manifest validation, hashing, versioning, lineage, and basic characterization.
7. Implement the tool registry, one local execution backend, and a small set of deterministic tools.
8. Implement experiment-plan compilation, budget estimates, decision gates, and structured run results.
9. Add MLflow through an adapter while keeping SQLite authoritative for operational state.
10. Implement a deterministic mock scientist provider, diagnostic packet, normalization, and privacy filtering.
11. Implement fixed static HTML report generation with explicit missing-section states and golden fixtures.
12. Implement append-only outcome events and current outcome status.
13. Prove the full flow with a small fixture point-cloud project and failure-path tests.
14. Add SSH execution after local execution and artifact contracts are stable.
15. Activate rule-based knowledge retrieval and governed knowledge proposals after operational records exist.

## Suggested Target Vertical Slice

The first usable milestone should be intentionally narrow and should extend the existing Wave 5b fixture path:

```text
one binary point-cloud fixture dataset
one canonical manifest format
one dataset validation command
one basic characterization tool
one baseline model tool
one error-analysis tool
one deterministic experiment planner
one deterministic decision gate
one local execution backend
one mock scientist provider
one SQLite database
one local MLflow artifact store
one static HTML report
one append-only outcome event
```

The milestone is complete only when a single OpenCode workflow, backed by reusable services, can produce a traceable report from the fixture dataset and when tests demonstrate blocked, failed, partial-success, and successful paths.

## Risks If Implementation Starts Without Closing P0 Gaps

- Agents may generate artifacts that look valid but use incompatible field names or taxonomies.
- Approval requirements may be bypassed because they remain comments rather than gates.
- Dataset, experiment, and report records may acquire incompatible identifiers and provenance conventions.
- Ad hoc scripts may become an accidental execution API before the tool registry exists.
- MLflow or Markdown may become an unintended source of truth for operational state.
- Provider-specific response formats may leak into the core before normalization is defined.
- A workflow engine may be built around underspecified manifests and later require redesign.
- Reports may solidify a data model that conflicts with experiment and decision contracts.
- Remote execution may duplicate state or authority before local execution semantics are stable.

## Overall Conclusion

The repository is well prepared for **designing** an agent-first AI research harness, but it is not yet prepared for **operating** one.

Its strongest assets are the authority model, evidence-oriented philosophy, modular workflows, subsystem documentation, and restrained MVP direction. Those should be preserved.

The main work ahead is to turn the documented boundaries into enforced contracts and a minimal executable vertical slice. The first objective should not be broad model support or sophisticated agent autonomy. It should be a small, deterministic, fully traceable workflow in which every handoff is typed, every action is gated, every artifact has provenance, every failure is recorded, and a human can review the result in a fixed report.
