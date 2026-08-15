# 05_MEMORY_SYSTEM.md

## Purpose

This document defines how LASI remembers work across projects.

The memory system is responsible for separating operational records from institutional learning, retrieving relevant prior context, supporting similarity bootstrap, preserving lessons, and preventing unsupported conclusions from becoming permanent knowledge.

It does not define dataset storage, experiment execution, report templates, scientist-provider prompts, or approval governance in detail. Those belong in separate LASI documents.

The memory system answers:

> What happened before, what did we learn from it, and how should that influence the next project?

## Assignment Control Memory

SQLite is LASI's working and episodic memory. Current-state tables store the
assignment, task DAG, dependencies, ready state, leases, attempts, plans,
decisions, budgets, and active frontier. Append-only assignment and task events
store the ordered episode: proposal, validation, queueing, lease, start, result,
runtime acceptance, retry, failure, criticism, timing, and token receipt. This is
sufficient to resume after process or machine shutdown; an OpenCode transcript
or Markdown handoff is never the source of truth.

Deterministic runtime-preflight failures are recorded as `assignment_runtime_blocked`, not as repeated coordinator errors. They preserve the exact diagnostic while leaving coordinator-turn and retry counters unchanged.

Pending escalation notifications are durable operational artifacts under `.lasi/notifications/`. They bridge the background runner to the OpenCode UI but do not replace the assignment record or `AssignmentEvent` as authority. Publication success or failure is itself recorded as an assignment event.

---

## Core Idea

LASI uses memory to reduce repeated waste.

The system should remember which experiments were run, which tools helped, which recommendations were useful, which dataset changes mattered, which projects were deployed, which projects failed, and which lessons were learned.

However, LASI should not treat every past result as universal truth.

A result from one project is evidence.

A repeated pattern across projects is a lesson candidate.

A reviewed and approved lesson may become institutional knowledge.

A hypothesis becomes a fact only through governance.

The memory system should preserve this distinction.

---

## Memory Types

LASI uses several related but distinct forms of memory.

LASI separates working, episodic, procedural, semantic, associative, artifact,
and context memory:

```text
SQLite current tables       = working memory / what is active now
SQLite append-only events   = episodic memory / what happened in order
Runtime services            = procedural memory / how work advances
Governed Git Markdown       = semantic memory / what LASI says it knows
Typed knowledge nodes/edges = associative memory / how knowledge relates
Artifact store              = artifact memory / what work produced
ICM snapshots               = context projection / what one agent needs now
```

The knowledge graph is a governed associative projection. It does not lease
tasks or replace SQLite transactions. Proposed claims and criticisms may enter
the graph with tentative status; accepted facts and policies still require the
knowledge-governance path.

### Operational Memory

Operational memory records what happened.

It belongs primarily in the database and MLflow.

Operational memory includes project records, dataset versions, dataset characterizations, experiment plans, tool runs, metrics, artifacts, scientist reviews, local decisions, remote execution logs, project outcomes, and artifact references.

Operational memory should be structured, queryable, auditable, and tied to stable identifiers.

It answers:

> What happened?

Examples:

```text
Project scratch_001 used dataset scratch_pointcloud:v0.3.0.
Experiment exp_014 trained PointNet with engineered arc features.
Validation F1 was 0.91.
Short-arc recall was 0.76.
The run used SSH host gpu_box_01.
The project was validated but not deployed.
```

### Semantic Memory

Semantic memory records what was learned.

It belongs primarily in the Git-backed markdown knowledge layer.

Semantic memory includes lessons learned, label policies, diagnostic rules, deployment retrospectives, literature summaries, toolbox guidance, active hypotheses, retired hypotheses, and approved facts.

Semantic memory should be human-readable, reviewable, version-controlled, and retrievable by LASI when building scientist-review context.

It answers:

> What did we learn?

Examples:

```text
Short low-point-count arcs have repeatedly caused label ambiguity in scratch point-cloud projects.

PointNet with engineered arc features has been useful on sparse point-cloud scratch datasets, but only when the label policy is stable.

Human review should precede larger architecture sweeps when multiple architectures plateau on mixed-label clusters.
```

### Artifact Memory

Artifact memory stores produced files.

It belongs primarily in MLflow or the artifact store.

Artifact memory includes plots, embeddings, cluster outputs, trained models, reports, predictions, logs, sample grids, characterization artifacts, environment snapshots, and generated HTML reports.

It answers:

> What was produced?

### Outcome Memory

Outcome memory records what ultimately happened to a project.

It belongs in structured form in the database and, when useful, in markdown retrospectives.

Outcome memory includes deployed, validated-not-deployed, cancelled, blocked, abandoned, failed-validation, failed-in-production, successful-in-production, superseded, and research-only outcomes.

It answers:

> Did this work actually matter?

Outcome memory is critical because a model that validates well but fails in production should not be treated as a success pattern.

---

## Memory Separation

LASI should not collapse memory types into one store.

The database is not a good place for long-form institutional beliefs.

Markdown is not a good place for metrics and lineage queries.

MLflow is not a good place for policy decisions.

The correct separation is:

```text
Database
└── Operational Memory

MLflow / Artifact Store
└── Artifact Memory

Git-backed Knowledge Layer
└── Semantic Memory

Project Outcome Ledger
└── Outcome Memory
```

These stores should reference each other through stable IDs, artifact URIs, document paths, and Git commit hashes.

### Token Usage Ledger

Token usage is operational telemetry, not an estimate or a semantic lesson. The
database stores an append-only entry for every durable action, tied to its
project, action identifier, action type, provider profile, model, and source
receipt. A `reported` entry may contain only token counts and billed cost
returned by the provider or agent runtime. LASI must not infer tokens from text,
ask an LLM to estimate them, or derive a billed price from published pricing.

Actions that do not invoke a token-metered runtime are recorded as
`not_applicable`; actions whose provider/runtime omitted the authoritative
receipt are recorded as `not_available` with a reason. Project and portfolio
summaries must retain these coverage states alongside totals so missing telemetry
cannot be mistaken for zero usage.

---

## Why Separation Matters

A metric is not a lesson.

A hypothesis is not a fact.

A project outcome is not the same thing as a validation score.

A deployment failure is not just another experiment result.

A label policy is not a model recommendation.

Memory separation prevents LASI from confusing evidence, interpretation, and authority.

---

## Experiment Memory

Experiment memory is the part of operational memory that records what was tried and what happened.

It includes:

```text
experiment_id
project_id
dataset_version
experiment_type
hypothesis
tool_runs
parameters
execution_backend
metrics
artifacts
result_summary
diagnostic_value
```

Experiment memory should preserve the reason for the experiment, not just the output.

For example, the system should know whether a larger model was trained to test model capacity, to establish a baseline, or because a similar dataset previously benefited from a larger model.

The same action can mean different things depending on why it was run.

---

## Recommendation Memory

Recommendation memory records what the scientist provider or local system recommended and what happened next.

It should track:

```text
recommendation_id
source
project_id
diagnosis
confidence
recommended_action
expected_value
accepted_or_rejected
executed_or_not
result
diagnosis_confirmed
diagnosis_weakened
diagnosis_contradicted
outcome_notes
```

This allows LASI to learn whether recommendations were useful.

A recommendation can be useful even if performance does not improve. For example, recommending human review may confirm that the dataset is label-policy limited and prevent wasted model training.

---

## Tool Usefulness Memory

Tool usefulness memory records how useful tools have been in context.

It should not assign one global usefulness score to a tool. A tool may be useful for one dataset type and low-value for another.

Tool usefulness should be tracked by problem type, modality, dataset characteristics, and experiment purpose.

Examples:

```text
HDBSCAN was useful for identifying mixed-label clusters in point-cloud scratch datasets.

Large transformer sweeps were low-value before label review on short-arc ambiguity problems.

Engineered arc features improved recall when point-cloud samples were sparse and labels were stable.
```

The system should distinguish between tools that improve metrics and tools that improve understanding.

---

## Dataset Similarity Memory

Dataset similarity memory helps LASI ask:

> Have we seen a dataset like this before?

Similarity should begin with structured dataset characterizations.

Relevant comparison dimensions include modality, problem type, sample count, class balance, primitive distributions, cluster structure, class-overlap score, label ambiguity indicators, coverage gaps, quality profile, metadata distribution, and benchmark role.

Later, similarity should also consider semantic memory.

For example, two datasets may be numerically similar, but one may come from a process area with known label-policy instability. That knowledge should influence the recommendation.

---

## Similarity Bootstrap

Similarity bootstrap is the process of using prior similar projects to choose an initial experiment path.

Instead of always starting with a generic baseline sweep, LASI may ask:

```text
Have we seen a similar dataset?
What architecture worked?
What diagnostics were useful?
What actions wasted compute?
What failure modes appeared?
Was the final project deployed, cancelled, or failed in production?
```

If a prior approach worked well on similar datasets, LASI may run it as a confirmation probe.

If it fails, that failure becomes diagnostic evidence.

The similarity prior should never be treated as proof.

---

## Memory Retrieval for Scientist Review

Before requesting a scientist review, LASI should retrieve relevant memory.

The scientist provider should receive the current diagnostic packet plus carefully selected context.

Relevant context may include:

```text
similar prior projects
similar dataset characterizations
historical best approaches
known low-value actions
relevant lessons
active hypotheses
label policies
diagnostic taxonomy entries
deployment outcomes
toolbox guidance
literature summaries
```

The retrieved context should be recorded as part of the review.

This makes the scientist review auditable. A later reviewer should be able to see which past evidence and institutional knowledge influenced the recommendation.

---

## Retrieval Discipline

More memory is not always better.

The memory system should retrieve relevant, bounded, and traceable context.

A scientist provider that receives too much context may overfit to irrelevant prior work or miss the current evidence.

The retrieval system should prefer:

```text
current project evidence first
approved policies over lessons
facts over hypotheses
recent similar projects over old unrelated projects
successful production outcomes over validation-only successes
contradictions and caveats over only positive examples
```

The system should not hide contradictory evidence.

If prior similar projects disagree, that disagreement should be surfaced.

---

## Operational Memory Store

The operational memory store should begin as SQLite and may later move to Postgres.

It should contain structured records for projects, datasets, dataset versions, characterizations, experiment plans, tool runs, remote runs, scientist reviews, local decisions, project outcomes, artifacts, recommendation outcomes, and tool usefulness.

The operational store should support queries such as:

```text
Show prior scratch point-cloud projects with high short-arc ambiguity.

Show experiments where larger models improved training loss but not validation performance.

Show projects that validated successfully but were not deployed.

Show tools that failed frequently on point-cloud datasets.

Show dataset updates that confirmed a data-coverage diagnosis.
```

---

## Semantic Memory Store

The semantic memory store should be a Git-backed markdown repository.

Recommended structure:

```text
knowledge/
├── facts/
├── policies/
├── hypotheses/
├── lessons/
├── literature/
├── toolbox/
├── taxonomies/
└── templates/
```

The semantic store should support human review.

A lesson should not become a fact just because an agent wrote it.

A hypothesis should not become policy without approval.

A deployment failure should be able to trigger a review of prior lessons.

---

## Knowledge Document Metadata

Each knowledge document should have metadata.

A simple markdown front matter block is sufficient:

```yaml
---
document_id: lesson_short_arc_ambiguity
type: lesson
status: approved
owner: process_ai_team
created_at: 2026-05-29
last_reviewed_at: 2026-05-29
source_projects:
  - scratch_001
  - scratch_004
related_modalities:
  - point_cloud
related_problem_types:
  - scratch_classification
tags:
  - label_ambiguity
  - short_arc
  - point_cloud
---
```

This metadata allows the retrieval system to select relevant documents without treating the knowledge repository as unstructured text only.

---

## Knowledge Proposals

The system should use proposals for semantic-memory changes.

A knowledge proposal may suggest:

```text
new lesson
policy update
fact creation
hypothesis promotion
hypothesis retirement
literature summary
toolbox note
contradiction warning
obsolete-lesson warning
```

The knowledge curator may draft proposals, but humans approve high-consequence knowledge changes.

This prevents one project or one scientist-provider response from rewriting institutional memory.

---

## Memory and Project Outcomes

Project outcomes should influence memory.

A project with `successful_in_production` status should carry more weight than a project that only validated offline.

A project marked `failed_in_production` should trigger review of any lessons, policies, or similarity priors that depended on it.

A project marked `cancelled` may still produce useful lessons, especially if cancellation revealed label instability, missing data, privacy constraints, unavailable tooling, or lack of operational value.

Outcome status should not be treated as an afterthought. It is part of memory quality.

---

## Memory Quality

The memory system should track confidence and status.

Suggested semantic statuses:

```text
draft
under_review
approved
tentative
contradicted
superseded
retired
```

Suggested evidence levels:

```text
single_project_observation
repeated_project_pattern
human_confirmed
production_confirmed
literature_supported
contradicted_by_later_result
```

A lesson based on one project should not be treated the same as a production-confirmed pattern across many projects.

---

## Memory Drift Risks

The memory system has risks.

The first risk is false generalization. A result from one dataset may be over-applied to unrelated datasets.

The second risk is stale knowledge. A lesson may become obsolete after toolbox changes, process changes, or new data.

The third risk is survivorship bias. Successful projects may be better documented than failures.

The fourth risk is model-induced authority. A scientist provider may phrase a hypothesis as if it were settled fact.

The fifth risk is contradiction accumulation. Markdown knowledge can become inconsistent if proposals are not reviewed.

The memory system should be designed to surface these risks rather than hide them.

---

## Memory Update Flow

A normal memory update flow is:

```text
Project produces results
↓
Database records operational facts
↓
MLflow stores artifacts
↓
Outcome ledger records project disposition
↓
Knowledge curator drafts possible lessons
↓
Human reviews proposed knowledge update
↓
Approved knowledge is committed to Git
↓
Future retrieval can use the knowledge document
```

This flow keeps operational records and semantic knowledge connected but distinct.

---

## Memory Retrieval Flow

A normal memory retrieval flow is:

```text
Current project state is loaded
↓
Dataset characterization is summarized
↓
Relevant prior projects are queried from operational memory
↓
Relevant knowledge documents are retrieved
↓
Conflicting or cautionary evidence is included
↓
Diagnostic packet is assembled
↓
Scientist provider receives bounded context
↓
Review records which memory was used
```

This flow prevents the scientist provider from reasoning only from the current run while also preventing unbounded retrieval.

---

## Core Memory Scope

The memory system should remain as simple as its retrieval and governance requirements allow.

It should include:

```text
structured operational records in SQLite
MLflow artifact references
project outcome status
basic scientist review history
basic tool run history
simple knowledge folder support
manual knowledge documents
mocked retrieval or rule-based retrieval
```

The core memory system uses a relational knowledge-graph projection and does not require a dedicated graph database, learned retrieval model, automatic lesson approval, or sophisticated similarity scoring without demonstrated need.

A small amount of structured memory used correctly is better than a large amount of vague memory used inconsistently.

---

## Later Memory Abilities

Later versions may add:

```text
vector search over knowledge documents
embedding search over dataset characterizations
similar-project retrieval
lesson contradiction detection
tool usefulness scoring
automatic knowledge proposal drafting
deployment-outcome weighting
learned dataset similarity
sabbatical memory review
foundation-opportunity memory scans
```

These should be added after the basic memory contracts are stable.

---

## Unsettled Questions

The first unsettled question is how much memory retrieval should be automated. Retrieval should remain inspectable and rule-based until a more advanced method demonstrates better evidence selection.

The second unsettled question is how to weight prior projects. Production-confirmed success should matter more than validation-only success, but the exact weighting is not yet defined.

The third unsettled question is how to handle contradictory lessons. The system should surface contradictions rather than choose one silently.

The fourth unsettled question is when a hypothesis becomes a fact. This should require governance.

The fifth unsettled question is when vector search provides enough retrieval benefit to justify another index and evaluation burden.

The sixth unsettled question is how to prevent stale knowledge from influencing future reviews. Periodic sabbatical review should help, but the exact mechanism is not defined.

The seventh unsettled question is how to represent memory confidence. It should probably combine evidence count, recency, human confirmation, production outcome, and contradiction history.

---

## Out of Scope for This File

This file does not define database schemas, vector-index implementation, Git workflow details, prompt templates, report layout, or approval authority.

Those belong in separate LASI documents.

This file defines how LASI thinks about memory and how memory should influence future research.
# Nested ICM and Structured Memory

LASI separates machine-native memory from semantic context. SQL operational
records, MLflow artifacts, telemetry, and future graph/vector stores remain the
structured sources of truth for events, metrics, relationships, and artifacts.
System ICM stores relatively stable institutional guidance under `system/`,
while project ICM stores isolated semantic state under `projects/<project_id>/`.
The context resolver retrieves a bounded subset of both layers for the current
action. Conversation history is not project memory unless a worker externalizes
the useful result as a durable artifact.

The minimum-sufficient-context rule is mandatory: no agent receives an entire
system or project workspace by default. Evidence claims link durable evidence to
claims and can be explicitly invalidated; invalidations are recorded under the
project evidence failures area. Promotion from project ICM to system ICM remains
a governed proposal, not an automatic copy.
