# AGENTS.md

## Purpose

This file is the entry point for agents working on LASI.

LASI stands for **Learning as a Service**.

LASI is an industrial ML research harness. Its purpose is not to blindly maximize model metrics. Its purpose is to help identify what limits ML performance, what evidence supports that diagnosis, what action should happen next, and whether further work is justified.

Agents working on LASI should treat this repository as a research operating system, not as a simple AutoML package.

---

## Agent Prime Directive

Preserve the distinction between:

```text
what happened
what was produced
what was learned
what is recommended
what is authorized
```

In LASI:

```text
Database             = operational memory / what happened
MLflow               = artifact memory / what was produced
Knowledge Layer      = semantic memory / what was learned
Scientist Provider   = recommendation layer / what may be true or useful
Decision System      = authorization layer / what may proceed
Reports              = communication layer / what humans review
Governance           = authority layer / what requires approval
```

Do not collapse these responsibilities into one subsystem.

---

## Required Reading Order

Before making architectural or behavioral changes, read these files in order (paths reflect current repo layout):

```text
_architecture/00_LASI_OVERVIEW.md
_architecture/01_ARCHITECTURE.md
_architecture/02_PROJECT_LIFECYCLE.md
_architecture/03_DATASET_SYSTEM.md
_architecture/04_EXPERIMENT_SYSTEM.md
_architecture/05_MEMORY_SYSTEM.md
_architecture/06_KNOWLEDGE_SYSTEM.md
_architecture/07_SCIENTIST_PROVIDER.md
_architecture/08_DECISION_SYSTEM.md
_architecture/09_REMOTE_EXECUTION.md
_architecture/10_REPORTING_SYSTEM.md
_architecture/11_OUTCOME_SYSTEM.md
_architecture/12_SABBATICAL_SYSTEM.md
_architecture/13_FOUNDATION_RECOMMENDER.md
_architecture/14_GOVERNANCE.md
_core/glossary.md
```

If a file does not exist yet, do not invent its contents silently. Create or update it explicitly.

For small implementation changes, read the directly relevant system file plus `_architecture/01_ARCHITECTURE.md` and this `AGENTS.md`.

---

## System Boundaries

Agents must respect LASI authority boundaries.

The scientist provider recommends. It does not execute.

The experiment planner translates recommendations into executable plans. It does not authorize high-risk work.

The decision system authorizes, blocks, escalates, stops, or converts recommendations into proposals.

The tool registry constrains what can run.

The dataset system owns dataset versions, lineage, comparability, benchmark roles, and dataset improvement proposals.

The experiment system owns controlled evidence generation.

The memory system separates operational memory from semantic memory.

The knowledge system owns Git-backed institutional knowledge.

The remote execution system runs approved work on remote compute while the local harness remains the source of truth.

The report system communicates findings through fixed static reports.

The outcome system records what ultimately happened to a project.

The sabbatical system proposes research-process improvements.

The foundation recommender identifies reusable representation opportunities but does not initiate training automatically.

The governance system defines approval requirements and high-consequence boundaries.

---

## Non-Negotiable Design Rules

### 1. LASI is OpenCode-first

The supported operating surface is OpenCode. A GUI is out of scope unless explicitly added later.

Users and agents operate LASI through OpenCode commands, agents, and skills. The command definitions live under `.opencode/command/`, specialist behavior under `.opencode/agent/` and `.opencode/skills/`, and workflow specifications under `_workflows/`.

OpenCode procedures should delegate to reusable Python service functions when implementation exists. Do not create a LASI application CLI as a competing operating surface, and do not put business logic in OpenCode command prompts.

---

### 2. LASI is provider-agnostic

Do not hard-code LASI to a specific frontier model or cloud provider.

Use the Scientist Provider abstraction.

Supported provider types may include:

```text
mock_provider
local_model
vertex
openai
anthropic
internal_api
future_provider
```

Every provider must normalize output into the same `ScientistReview` contract.

---

### 3. LASI is framework-neutral

Do not make PyTorch the dataset architecture.

PyTorch datasets, scikit-learn matrices, XGBoost matrices, FAISS indexes, Pandas DataFrames, NumPy arrays, and HTML review grids are runtime adapters.

The canonical dataset belongs to LASI.

The adapter belongs to the tool.

---

### 4. Raw data, canonical data, metadata, artifacts, and knowledge are different things

Do not use one storage layer for everything.

Use the intended separation:

```text
Raw Data Store          = original source exports
Canonical Dataset Store = versioned framework-neutral LASI data
Database                = metadata, lineage, state, decisions, outcomes
MLflow / Artifact Store = plots, embeddings, models, logs, reports
Knowledge Layer         = facts, policies, hypotheses, lessons, literature
Runtime Adapters        = tool-specific views
```

---

### 5. Reports are fixed-template artifacts

Do not generate reports as unconstrained LLM essays.

Reports should be static HTML generated from structured `StaticReportData`.

Every required section should render, even if the section status is `not_run`, `blocked_by_privacy`, `failed`, `partial_success`, or `deferred_to_later_phase`.

---

### 6. High-consequence actions require approval

Do not silently perform high-consequence changes.

High-consequence actions include:

```text
modify labels
create dataset versions
delete dataset samples
merge or split classes
change label policy
change benchmark definition
send raw data externally
change privacy policy
approve facts or policies
promote hypotheses to facts
deploy models
launch foundation-model training
update toolbox
change remote host trust profile
```

If in doubt, escalate or convert to a proposal.

---

### 7. Experiments must be planned before execution

A recommendation is not an executable command.

A recommendation should become an `ExperimentPlan`.

The decision system should evaluate the plan before tools run.

Tool runs must be logged, traceable, and connected to dataset version, tool version, execution backend, artifacts, and results.

---

### 8. Remote workers are not sources of truth

The local LASI harness owns project state, database writes, decision records, report generation, artifact registration, and knowledge updates.

Remote workers execute commands and return artifacts.

Do not design remote machines as independent LASI authorities.

---

### 9. Knowledge updates must be proposed before approval

The knowledge curator may draft lessons, retrospectives, literature summaries, contradiction warnings, and policy proposals.

It must not silently approve facts, policies, or hypothesis promotions.

Humans approve high-consequence knowledge changes.

---

### 10. Outcomes matter

A project is not complete just because experiments finished.

Every project should eventually have an outcome status.

Examples:

```text
pending
research_only
validated_not_deployed
deployed
successful_in_production
failed_validation
failed_in_production
cancelled
abandoned
blocked
superseded
archived
```

Future recommendations should distinguish validation-only success from production success.

---

## Expected Repository Structure

The exact implementation may evolve, but agents should prefer a structure similar to:

```text
services/
├── core/
├── configs/
├── datasets/
├── experiments/
├── tools/
├── providers/
├── decisions/
├── memory/
├── knowledge/
├── reports/
├── remote/
├── governance/
├── tests/
└── docs/
```

Documentation should remain modular.

Do not collapse all system behavior into one giant PRD.

---

## Documentation Files

The documentation is organized as system files.

Each file owns one concern.

### `00_LASI_OVERVIEW.md`

Defines LASI at the highest level.

### `01_ARCHITECTURE.md`

Defines major components and how they relate.

### `02_PROJECT_LIFECYCLE.md`

Defines project states and transitions.

### `03_DATASET_SYSTEM.md`

Defines dataset manifests, canonical storage, versioning, characterization, lineage, comparability, and dataset portfolio behavior.

### `04_EXPERIMENT_SYSTEM.md`

Defines experiment plans, tool runs, evidence generation, execution, and result interpretation.

### `05_MEMORY_SYSTEM.md`

Defines operational memory, semantic memory, artifact memory, outcome memory, retrieval, and similarity bootstrap.

### `06_KNOWLEDGE_SYSTEM.md`

Defines Git-backed markdown knowledge: facts, policies, hypotheses, lessons, literature, toolbox notes, taxonomies, templates, and knowledge proposals.

### `07_SCIENTIST_PROVIDER.md`

Defines the model-provider abstraction, provider profiles, `ScientistReview`, normalization, provider errors, privacy, and mock providers.

### `08_DECISION_SYSTEM.md`

Defines authorization, risk levels, policy checks, approval gates, blocking, stopping, and escalation.

### `09_REMOTE_EXECUTION.md`

Defines SSH-backed execution, host profiles, staging, remote workspaces, environment validation, log capture, artifact retrieval, and cleanup.

### `10_REPORTING_SYSTEM.md`

Defines fixed static HTML reports, `StaticReportData`, missing-section handling, provenance, and report artifacts.

### `11_OUTCOME_SYSTEM.md`

Defines project outcome statuses, outcome events, deployment outcomes, production failures, and how outcomes affect future memory.

### `12_SABBATICAL_SYSTEM.md`

Defines periodic review of outcomes, tools, policies, hypotheses, literature, and system assumptions.

### `13_FOUNDATION_RECOMMENDER.md`

Defines how LASI identifies reusable foundation or self-supervised representation opportunities.

### `14_GOVERNANCE.md`

Defines approval authority, high-consequence actions, proposals, policies, overrides, exceptions, and audit trails.

### `_core/glossary.md`

Defines canonical terms.

Agents should update the relevant document when behavior changes.

---

## Implementation Expectations

### Prefer contracts before behavior

Before implementing a workflow, define or update the relevant contract.

Important contracts include:

```text
ProjectConfig
DatasetManifest
DatasetVersion
DatasetCharacterization
ToolSpec
ToolRunResult
ExperimentPlan
RemoteRunSpec
DiagnosticPacket
ScientistReview
DecisionRecord
ProjectOutcome
KnowledgeDocument
KnowledgeProposal
StaticReportData
```

Do not let implicit dictionaries spread through the codebase.

Use typed schemas.

---

### Prefer small services over giant orchestrators

Avoid a single massive coordinator class.

Prefer focused services:

```text
DatasetService
ExperimentPlanner
ToolRunner
RemoteRunner
ScientistProviderClient
DecisionService
ReportService
OutcomeService
KnowledgeRetriever
KnowledgeCurator
```

The harness core should coordinate these services, not absorb them.

---

### Preserve provenance

When generating outputs, preserve where they came from.

Every important artifact should trace to:

```text
project_id
dataset_version
experiment_id
tool_run_id
scientist_review_id
decision_id
report_id
knowledge_document_refs
artifact_uri
```

If provenance is unclear, fix it before adding features.

---

### Make missing states explicit

Do not hide missing information.

Use explicit statuses such as:

```text
not_run
not_available
not_applicable
blocked_by_privacy
blocked_by_policy
blocked_by_budget
failed
partial_success
deferred_to_later_phase
```

This applies especially to reports and diagnostic packets.

---

### Treat failures as evidence

Failed runs, blocked actions, cancelled projects, invalid provider responses, missing artifacts, and production failures are not garbage.

They are operational evidence.

Record them with structured failure reasons.

---

## Testing Requirements

Every implementation should be testable without external model providers.

The mock scientist provider is required.

Prefer tests that cover:

```text
schema validation
dataset validation
experiment plan compilation
decision gate behavior
tool run success
tool run partial success
tool run failure
remote execution with mock or loopback host
artifact retrieval
report generation
provider response normalization
knowledge retrieval
outcome updates
```

Use golden report fixtures for reporting behavior.

Do not require real SSH hosts, real GPUs, or real model-provider API calls for core test suites.

---

## Remote Execution Rules

When implementing remote execution:

1. The local harness remains authoritative.
2. Remote jobs execute explicit run bundles.
3. Every remote run records host profile, command, environment setup, logs, artifacts, and exit status.
4. Missing artifacts are structured failures or partial successes.
5. Raw data transfer must obey privacy and governance policies.
6. Remote datasets may be cached later, but the cache is not the source of truth.

---

## Scientist Provider Rules

When implementing scientist-provider behavior:

1. Always support a mock provider.
2. Normalize every provider response into `ScientistReview`.
3. Validate schema before using the response.
4. Record raw response as an artifact.
5. Record provider profile and prompt/template version.
6. Reject unsupported action types.
7. Do not allow provider output to bypass the decision system.
8. Do not let the provider modify datasets, tools, reports, or knowledge directly.

---

## Dataset Rules

When implementing dataset behavior:

1. Store datasets as framework-neutral versioned assets.
2. Do not store datasets as PyTorch `Dataset` objects.
3. Use runtime adapters for PyTorch, scikit-learn, XGBoost, FAISS, Pandas, NumPy, review grids, and other tool-specific views.
4. Every experiment references a dataset version.
5. Dataset changes create lineage.
6. Comparability must be explicit.
7. Benchmarks are protected assets.
8. Label-policy changes require approval.

---

## Knowledge Rules

When implementing knowledge behavior:

1. Use Git-backed markdown for semantic memory.
2. Use front matter for knowledge metadata.
3. Separate facts, policies, hypotheses, lessons, literature, toolbox notes, taxonomies, and templates.
4. Treat hypotheses as hypotheses.
5. Treat contradicted lessons as cautionary context.
6. Record which knowledge documents are retrieved for scientist reviews.
7. Use proposals for high-consequence knowledge changes.
8. Humans approve facts and policies.

---

## Reporting Rules

When implementing reporting:

1. Reports are static HTML artifacts.
2. Reports are generated from structured `StaticReportData`.
3. Reports must show missing, blocked, failed, or deferred sections explicitly.
4. Reports must include scientist review and decision record when available.
5. Reports must include project outcome status.
6. Reports must show relevant knowledge context when used.
7. Reports used for review should be immutable artifacts.

---

## Commit and Change Guidance

When changing LASI:

1. Identify which system file owns the behavior.
2. Update documentation before or alongside code.
3. Add or update schema tests.
4. Add or update service tests.
5. Add or update report fixtures if output changes.
6. Preserve backward compatibility where possible.
7. Record unresolved design questions in the relevant document.
8. Do not introduce a new source of truth without documenting it.

---

## Red Flags

Agents should stop and reassess if they are about to:

```text
hard-code one scientist provider
make PyTorch the dataset abstraction
store metrics only in markdown
store lessons only in the database
let a provider execute tools directly
let reports invent their own structure
silently skip failed sections
modify labels without approval
overwrite benchmark data
create dataset versions without lineage
send raw data externally without decision approval
treat validation success as production success
approve generated knowledge without review
```

These are architecture violations.

---

## How to Handle Uncertainty

If a design choice is unsettled:

1. Prefer the simplest reversible implementation.
2. Preserve the boundary that lets the choice change later.
3. Document the open question.
4. Do not overbuild infrastructure before the contract is stable.
5. Do not hide assumptions in code.

Examples:

```text
Use SQLite before Postgres unless concurrency requires Postgres.
Use SSH before Slurm or Kubernetes unless workload requires scheduling.
Use rule-based retrieval before vector search unless scale requires semantic search.
Use mock provider before real provider integration.
Use static reports before dashboards.
```

---

## MVP Bias

The MVP should prove the harness spine.

The MVP should include:

```text
OpenCode command, agent, and skill operation
project config
dataset manifest
dataset validation
dataset characterization
SQLite operational database
MLflow artifact logging
tool registry
baseline experiments
SSH remote execution
mock scientist provider
one real or local scientist provider if practical
decision gate
static HTML report
project outcome status
basic knowledge folder support
tests
```

The MVP should not include:

```text
GUI
full AutoML
full hyperparameter optimization
foundation model training
automatic deployment
complex vector database
knowledge graph database
multi-provider voting
advanced governance workflow
full production monitoring
```

---

## Final Instruction

When in doubt, preserve LASI’s core structure:

```text
Evidence first.
Contracts before behavior.
Recommendations are not commands.
Reports are fixed artifacts.
Datasets are versioned assets.
Knowledge is governed.
Outcomes matter.
Humans approve high-consequence changes.
```
