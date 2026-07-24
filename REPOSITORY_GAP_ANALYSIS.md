# LASI Repository Gap Analysis

## Purpose

This document compares the current LASI repository with the architecture described in `AGENTS.md`, `_architecture/`, `_core/`, `_workflows/`, `_skills/`, `_schemas/`, and `_templates/`.

The assessment is limited to repository structure and implementation readiness for agent-first AI model development and experimentation. It does not propose changing LASI's authority boundaries, and it does not implement or reorganize anything.

## Executive Assessment

LASI is currently a strong **architecture, governance, and agent-procedure scaffold**, but it is not yet an executable AI engineering workspace.

The repository already describes the intended operating model unusually well:

- Evidence is separated from interpretation, recommendation, authorization, and institutional knowledge.
- Scientist providers recommend but do not execute.
- Experiments require plans and decisions before execution.
- Datasets are intended to be framework-neutral, versioned assets.
- Reports are fixed, structured artifacts rather than unconstrained model prose.
- Outcomes and failures are treated as evidence.
- High-consequence actions require human approval.

The principal gap is that these boundaries exist only in documentation, templates, and a small set of incomplete schemas. There is no executable harness connecting project intake, dataset validation, experiment planning, decision gates, tool execution, artifact tracking, scientist review, reporting, outcomes, and knowledge curation.

In practical terms, a general-purpose agent can read the repository and manually follow its instructions, but the repository itself cannot yet validate, authorize, execute, record, reproduce, or report an ML experiment.

## Current Repository State

| Area | Current state | Readiness |
|---|---|---|
| Architecture | Fifteen subsystem documents in `_architecture/` | Strong conceptual foundation |
| Agent policy | Detailed operating rules in `AGENTS.md` and `_core/authority_boundaries.md` | Strong procedural foundation |
| Workflows | Five workflow definitions with ordered `STEP.md` files | Declarative only |
| Skills | Nine skill packs with instructions, contracts, checklists, and examples | Human/agent guidance only |
| Schemas | Five YAML schemas | Partial and inconsistent |
| Templates | Markdown templates for major artifacts | Manual scaffolding |
| Knowledge | Correct category structure with README placeholders | Empty semantic-memory scaffold |
| Tickets | Filesystem lifecycle folders with README placeholders | Empty manual queue scaffold |
| Projects | README describing a project folder convention | No project instances |
| Tools | Only step-document guidelines | No executable tools or registry |
| Scripts | README explicitly excluding runtime scripts | No automation |
| Application code | None | Not started |
| Tests | None | Not started |
| CI and developer tooling | None | Not started |
| Git repository | Workspace is not currently a Git repository | Required foundations unavailable |

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

The `_skills/` and `_workflows/` trees provide bounded procedures for dataset intake, characterization, experiment planning, remote execution, scientist review, decision review, reporting, outcome recording, and knowledge curation.

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

### 1. No executable harness spine

The target architecture names a CLI, harness core, tool registry, experiment planner, remote runner, scientist provider, decision system, report generator, database, MLflow integration, and knowledge curator. None of these components has an implementation.

There is no code path that can perform the minimum end-to-end sequence:

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

Until this spine exists, LASI remains a specification rather than a working research operating system.

### 2. No source-package structure

The expected implementation structure in `AGENTS.md` is absent. There is no `lasi/` package or equivalent source tree containing reusable services.

Missing structural areas include:

```text
lasi/cli/
lasi/core/
lasi/configs/
lasi/datasets/
lasi/experiments/
lasi/tools/
lasi/providers/
lasi/decisions/
lasi/memory/
lasi/knowledge/
lasi/reports/
lasi/remote/
lasi/governance/
tests/
```

The underscore-prefixed directories currently hold specifications and agent instructions; they do not substitute for implementation modules.

### 3. No CLI despite the CLI-first requirement

`AGENTS.md` and `_architecture/01_ARCHITECTURE.md` define the CLI as the operating surface, but there is no package entry point or command implementation.

At minimum, the target design implies commands for project creation/status, dataset validation and characterization, experiment planning and execution, decision review, provider review, report generation, outcome updates, and SSH diagnostics. None currently exists.

This also means agents do not have a stable, bounded interface through which to operate LASI. Their only available interface is direct file manipulation guided by Markdown.

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

There is also no schema validator, typed-model package, schema versioning mechanism, migration policy, or contract test suite.

### 5. Existing schemas, templates, and examples disagree

The current contract artifacts are not yet safe for automated agent use.

Specific inconsistencies include:

- `_schemas/static_report.schema.yaml` requires `executive_summary` but does not define that property.
- The static report schema expects generic content under `sections`, while `_templates/static_report/static_report_outline.md` places named sections at the top level.
- `_schemas/scientist_review.schema.yaml` requires `recommendations` and numeric confidence from 0 to 1, while the example uses `recommended_next` and `confidence: medium`.
- The scientist review schema omits most fields required by `_architecture/07_SCIENTIST_PROVIDER.md`, including diagnosis, evidence, counter-evidence, alternative hypotheses, stop recommendation, and knowledge references.
- `_templates/decision_record/decision_record_template.md` includes `action_requested` and `approval_required`, but the decision schema does not define them.
- `_schemas/experiment_plan.schema.yaml` defines `decision_record_required` as a boolean, while its template uses `yes`.
- The experiment plan schema defines `approval_required` as a string rather than a boolean or controlled decision object.
- Experiment-type values in the schema do not match the architecture's MVP taxonomy such as `baseline_probe`, `learning_curve`, `embedding_or_cluster_analysis`, and `error_analysis`.
- Privacy values in the experiment plan schema (`public`, `restricted`, `private`) do not match the privacy modes used by provider and governance documents.

Agent-first execution depends on strict machine-readable handoffs. These disagreements would cause agents, validators, services, and reports to interpret the same artifact differently.

### 6. No tool registry and no executable tools

The architecture assigns the tool registry responsibility for constraining what can run. `_tools/` currently contains only `STEP_MD_GUIDELINES.md`.

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

Without a registry, an agent cannot turn an approved plan into bounded execution. It can only invent or call ad hoc scripts, which the architecture explicitly seeks to avoid.

### 7. No operational memory

SQLite is repeatedly identified as the MVP source of operational truth, but no database, models, migrations, repositories, or services exist.

There is no durable structured record for projects, dataset versions, characterizations, experiment plans, tool runs, remote runs, scientist reviews, decisions, approvals, reports, outcomes, artifacts, recommendation results, or tool usefulness.

The filesystem ticket folders are not a substitute for operational memory because they provide no transactional state, referential integrity, query layer, event history, or enforcement of valid transitions.

### 8. No artifact memory or MLflow integration

MLflow is a core architectural component, but the repository has no dependency, configuration, tracking URI convention, logging adapter, run association, artifact resolver, or test fixture.

As a result, LASI cannot currently preserve or connect models, metrics, plots, predictions, embeddings, environment snapshots, provider responses, reports, or remote logs to their provenance records.

### 9. No dataset system implementation

The dataset architecture is extensive, but the repository has no canonical data store, raw-data layout, dataset service, immutable version records, hashing, lineage enforcement, comparability checks, benchmark protection, or runtime adapters.

The manifest schema is also too minimal for the first documented point-cloud use case. It defines a generic file list but not a sample-level contract with IDs, labels, point-cloud references, metadata, and splits.

The repository therefore cannot yet guarantee the central rule that every result is tied to an identified, validated, comparable dataset version.

### 10. No experiment planning or execution implementation

There is no deterministic plan compiler, evaluation policy, duplicate-run detection, budget calculation, local execution backend, result normalization, reproducibility record, or diagnostic packet builder.

Workflow manifests identify phases but have no workflow engine to parse dependencies, validate preconditions, persist state, resume work, enforce approval points, or route handoffs.

### 11. Governance is documented but not enforced

The decision and governance documents clearly define risk levels, approval requirements, proposal conversion, policy checks, overrides, and exceptions. No implementation enforces these rules.

Approval flags in workflow files and templates are currently documentary. An agent can bypass them because there is no gate between a plan and execution, no approval record store, no policy evaluator, and no command authorization layer.

For an agent-first workspace, unenforced governance is a major gap: written safety boundaries are useful guidance but do not create runtime control.

### 12. No scientist-provider abstraction or mock provider

There is no provider interface, provider profile loader, privacy filter, diagnostic-packet serializer, response normalizer, schema validator, raw-response recorder, or provider error handling.

The required deterministic mock provider is also absent. This blocks provider-independent tests of review, decision, report, and failure workflows.

### 13. No static report renderer

The target report is fixed static HTML generated from typed `StaticReportData`. The repository currently has an outline and schema only.

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

### 14. No remote execution backend

SSH execution is specified but not implemented. There are no host profiles, trust checks, run bundles, environment validation, command execution, log capture, artifact retrieval, cleanup policies, checksums, or `doctor-ssh` command.

The absence of this layer means the workspace is not yet set up for agents to use larger CPU/GPU environments while retaining local authority and provenance.

### 15. Knowledge structure exists but contains no governed knowledge

The `knowledge/` tree correctly separates facts, policies, hypotheses, lessons, literature, toolbox notes, taxonomies, and templates. Each area currently contains only a README.

There are no front-matter-bearing knowledge documents, metadata validator, retrieval service, proposal registry, status enforcement, Git commit references, or tests for retrieval priority and contradictory knowledge.

In addition, the workspace is not a Git repository, so the intended Git-backed semantic memory has no history, review, or commit identity.

### 16. No outcome ledger

Outcome recording has a template and skill, but there is no `ProjectOutcome` schema, append-only event model, status-transition validation, persistence, query service, or CLI update command.

This prevents LASI from distinguishing validation-only success from production success in operational memory, despite that distinction being one of the system's core design goals.

### 17. No tests, fixtures, or continuous integration

There is no test directory or automated validation for schemas, workflows, skills, services, CLI behavior, reports, remote execution, or provider normalization.

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

### 18. No reproducible development environment

There is no language package manifest, dependency lock, environment example, configuration model, secrets guidance, task runner, container option, or bootstrap command.

An agent cannot reliably determine how to install, test, lint, or run LASI. This is a direct agent-first usability gap because every agent would have to infer or recreate the development environment.

### 19. No end-to-end reference project

There are synthetic artifact examples, but no small project demonstrates the intended vertical slice with a real or fixture dataset.

A reference project is needed to prove that all contracts join correctly across dataset version, plan, decision, tool run, artifacts, scientist review, report, and outcome. Without it, subsystem documents can remain individually plausible while integration gaps go undetected.

## Agent-First Development Gaps

The repository has good instructions for agents, but agent-first development requires more than agent-readable Markdown.

### Stable machine interfaces are missing

Agents need stable commands and typed inputs rather than permission to manipulate internal files directly. The CLI, service layer, schemas, and tool registry should become the bounded operating interface.

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
| P0 | Package, configuration, and CLI foundation | Establishes the supported operating surface |
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
3. Establish the package, configuration loader, thin CLI, test harness, and CI baseline.
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

The first usable milestone should be intentionally narrow:

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

The milestone is complete only when a single CLI workflow can produce a traceable report from the fixture dataset and when tests demonstrate blocked, failed, partial-success, and successful paths.

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
