# 06_KNOWLEDGE_SYSTEM.md

## Purpose

This document defines how LASI stores, retrieves, reviews, and governs institutional knowledge.

The knowledge system is responsible for semantic memory: facts, policies, hypotheses, lessons, literature summaries, toolbox guidance, diagnostic taxonomies, and templates.

It does not store raw experiment metrics, model artifacts, dataset lineage, or tool-run records. Those belong in the database and MLflow.

The knowledge system answers:

> What has LASI learned, what does the organization believe, what remains uncertain, and what guidance should influence future work?

---

## Core Idea

LASI should distinguish what happened from what was learned.

The database records what happened.

MLflow stores what was produced.

The knowledge layer records what the organization learned.

This distinction matters because a single experiment result should not automatically become institutional truth. A result may be a one-off observation, a tentative lesson, a hypothesis, a contradicted belief, or an approved fact.

The knowledge system exists to preserve learning without allowing unsupported claims to silently become policy.

---

## Knowledge Layer

The knowledge layer is a Git-backed markdown repository.

Markdown is used because it is readable by humans, easy for agents to retrieve, easy to diff, and easy to review through Git.

The knowledge layer should be structured enough for retrieval but simple enough for humans to maintain.

LASI also maintains typed knowledge nodes and edges for associative retrieval:
claims, experiments, evidence, criticisms, datasets, tools, outcomes, and their
relationships. This graph is not an independent operational authority. It is a
projection of accepted SQL events, artifact provenance, and governed Markdown.
Agent-created claims enter as proposed or challenged nodes; graph connectivity
does not promote them into facts.

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

Each folder represents a different epistemic status or use case.

The folder structure is not cosmetic. It tells agents and humans how strongly a document should be trusted.

---

## Knowledge Categories

### Facts

Facts are accepted truths or settled findings.

A fact should have stronger evidence than a one-off observation.

Examples:

```text
Point-cloud scratch projects currently use the labels scratch and non_scratch.

The primary LASI operating surface is OpenCode commands, agents, and skills, backed by reusable Python services.

Remote execution is handled through SSH in the minimum viable harness.
```

Facts should be used carefully. Promoting something to a fact should require review.

---

### Policies

Policies are decisions that guide behavior.

A policy may be based on evidence, risk tolerance, operational constraints, or organizational preference.

Examples:

```text
Raw proprietary samples may not be sent to an external scientist provider without explicit approval.

Label-policy changes require human approval.

A frozen benchmark should not be overwritten when class definitions change.
```

Policies are authoritative even when they are not universal scientific truths.

---

### Hypotheses

Hypotheses are active but unproven beliefs.

They should be easy to find, test, support, contradict, promote, or retire.

Examples:

```text
Short low-point-count arcs are a major source of label ambiguity in scratch point-cloud data.

PointNet plus engineered arc features may work well on sparse scratch point-cloud datasets.

Dataset characterization similarity may predict useful model families.
```

A hypothesis should never be treated as a fact just because it has existed for a long time.

---

### Lessons

Lessons are retrospective observations from prior work.

They may be tentative or approved.

Examples:

```text
Larger models did not help when all tested architectures plateaued on mixed-label short-arc clusters.

Human review was more valuable than additional tuning for scratch datasets with low-purity ambiguity clusters.

Dataset updates should be validated against the specific problem they were intended to fix.
```

Lessons should reference their source projects and outcomes.

---

### Literature

Literature documents summarize external research.

They should include the source, summary, relevance, limitations, and possible LASI implications.

Literature summaries are not automatically facts or policies. They are research inputs.

---

### Toolbox

Toolbox documents describe tools, diagnostics, models, adapters, and known tool failure modes.

Examples:

```text
when_to_use_hdbscan.md
pointnet_probe.md
learning_curve_diagnostics.md
remote_execution_runner.md
```

Toolbox documents help the scientist provider and local agent understand how tools should be used.

They should not replace the tool registry. The tool registry defines executable tools. Toolbox documents explain how and why to use them.

---

### Taxonomies

Taxonomies define controlled vocabulary.

Examples include limiter types, project outcome statuses, dataset change types, comparability statuses, experiment types, review statuses, and recommendation types.

Taxonomies help prevent vocabulary drift.

Example:

```text
label_ambiguity
data_coverage
model_capacity
representation_gap
domain_shift
benchmark_leakage
```

The database may store enum values, but the knowledge layer should explain what those values mean.

---

### Templates

Templates define reusable document and prompt structures.

Examples:

```text
scientist_review_prompt.md
deployment_review_template.md
lesson_template.md
sabbatical_review_template.md
static_report_section_template.md
```

Templates should be treated as knowledge assets because they shape system behavior.

---

## Knowledge Document Format

Knowledge documents should use markdown with front matter.

Example:

```markdown
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

# Short Arc Ambiguity in Scratch Point Clouds

## Claim

Short low-point-count arcs have repeatedly caused label ambiguity in scratch point-cloud classification projects.

## Evidence

...

## Limitations

...

## Implications

...
```

The front matter makes retrieval easier.

The markdown body makes the document useful to humans.

---

## Required Front Matter

A knowledge document should include enough metadata for retrieval and governance.

Recommended fields:

```yaml
document_id:
type:
status:
owner:
created_at:
last_reviewed_at:
source_projects:
source_datasets:
related_modalities:
related_problem_types:
related_tools:
tags:
evidence_level:
```

Not every field needs to be populated for every document, but the structure should be consistent.

---

## Knowledge Status

Knowledge documents should have status values.

Suggested statuses:

```text
draft
under_review
approved
tentative
contradicted
superseded
retired
```

Status affects how strongly a document should influence the scientist provider.

An approved policy should carry more authority than a tentative lesson.

A contradicted lesson should be retrieved as cautionary context, not positive guidance.

A retired document should remain available for history but should not guide new recommendations unless explicitly requested.

---

## Evidence Levels

Knowledge documents should describe the level of evidence behind them.

Suggested evidence levels:

```text
single_project_observation
repeated_project_pattern
human_confirmed
production_confirmed
literature_supported
contradicted_by_later_result
policy_decision
```

Evidence level is not the same as document type.

A lesson may be based on a single project or repeated production-confirmed outcomes.

A policy may be authoritative even if evidence is incomplete.

A hypothesis may be literature-supported but not yet validated internally.

---

## Knowledge Proposals

LASI should not let the scientist provider or knowledge curator silently rewrite institutional knowledge.

Changes should be proposed.

A knowledge proposal may recommend:

```text
new fact
new policy
new hypothesis
new lesson
new literature summary
new toolbox note
new taxonomy entry
new template
policy update
hypothesis promotion
hypothesis retirement
lesson retirement
contradiction warning
obsolete-knowledge warning
```

The proposal should include the source, evidence, risk, affected documents, and recommended action.

For solo use, approval may be lightweight. For team use, approval should happen through pull requests or review gates.

---

## Knowledge Curator

The knowledge curator drafts and maintains proposed knowledge updates.

It may be model-assisted, deterministic, or both.

The curator can draft:

```text
lesson summaries
project retrospectives
deployment reviews
literature summaries
toolbox notes
hypothesis updates
policy-change proposals
contradiction warnings
stale-document warnings
```

The curator proposes.

Humans approve.

This boundary prevents LASI from turning one model’s interpretation into institutional memory without review.

---

## Knowledge Retrieval

Knowledge retrieval selects relevant documents for a current task.

Before a scientist review, LASI should retrieve relevant facts, policies, hypotheses, lessons, literature, toolbox guidance, taxonomies, and templates.

Retrieval should be bounded and auditable.

The scientist review should record which knowledge documents were included.

This allows future reviewers to understand why the scientist provider reached a recommendation.

---

## Retrieval Priority

Not all knowledge should be weighted equally.

A reasonable retrieval priority is:

```text
active project evidence
approved policies
approved facts
relevant taxonomies
production-confirmed lessons
human-confirmed lessons
similar-project lessons
active hypotheses
literature summaries
toolbox notes
retired or contradicted documents, when relevant as cautions
```

The system should not retrieve only positive supporting evidence. Contradictory or cautionary knowledge may be more important than confirming examples.

---

## Knowledge and Scientist Reviews

The scientist provider should not reason only from current experiment evidence when relevant prior knowledge exists.

A scientist review should receive:

```text
diagnostic packet
relevant approved policies
relevant facts
relevant lessons
active hypotheses
relevant taxonomy definitions
relevant toolbox guidance
relevant literature summaries
similar project outcomes
```

However, the provider should not be given unlimited knowledge context.

Too much context creates noise and increases the risk that old or irrelevant knowledge overrides current evidence.

The retrieved context should be focused and traceable.

---

## Knowledge and Reports

Static reports should include a knowledge context section when knowledge was used.

This section should list the most relevant knowledge documents, their type, status, and how they influenced the review.

Example:

```text
Knowledge Used:
- policy_external_model_data_transfer.md
- lesson_short_arc_ambiguity.md
- taxonomy_performance_limiters.md
```

The report should not hide the knowledge basis for a recommendation.

---

## Knowledge and Project Outcomes

Project outcomes should update knowledge.

A successful production deployment may strengthen a lesson.

A failed production deployment may contradict a lesson or trigger a policy review.

A cancelled project may still produce valuable knowledge if cancellation revealed missing data, unstable labels, privacy barriers, tooling gaps, or lack of operational value.

The outcome ledger and knowledge layer should remain connected.

---

## Knowledge and Sabbatical Review

Sabbatical review should examine the knowledge layer periodically.

It should ask:

```text
Which lessons are stale?
Which hypotheses have enough evidence to promote?
Which facts have been contradicted?
Which policies caused friction?
Which literature summaries suggest toolbox updates?
Which deployment failures should change our beliefs?
```

Sabbatical review should produce knowledge proposals, not direct edits.

The core question is:

> What should the organization believe differently now?

---

## Knowledge Governance

Knowledge governance defines authority.

Important governance questions include:

```text
Who can create facts?
Who can approve facts?
Who can approve policies?
When does a hypothesis become a fact?
How are contradictory lessons resolved?
How are obsolete lessons retired?
Can a deployment failure invalidate a lesson?
How are literature summaries reviewed?
Who owns taxonomy changes?
```

A reasonable early rule is:

```text
The curator may draft.
The scientist provider may recommend.
Humans approve high-consequence knowledge changes.
```

High-consequence knowledge changes include facts, policies, hypothesis promotions, benchmark-policy changes, and label-policy changes.

---

## Git Workflow

The knowledge layer should be Git-backed.

Git provides history, diffs, rollback, review, and authorship.

For solo use, direct commits may be acceptable.

For team use, knowledge updates should use pull requests or an equivalent review workflow.

The database should record the Git commit hash for knowledge documents used in scientist reviews when possible.

This makes recommendations reproducible and auditable.

---

## Knowledge Drift Risks

The knowledge system has several risks.

The first is hypothesis hardening. A hypothesis may become treated as fact simply because it is old.

The second is stale knowledge. A lesson may remain in use after tooling, process conditions, datasets, or production environments change.

The third is contradiction accumulation. Multiple lessons may conflict without anyone noticing.

The fourth is over-retrieval. The scientist provider may receive too much context and become distracted from current evidence.

The fifth is authority leakage. A model-generated lesson may be treated as approved human knowledge.

The sixth is survivorship bias. Successful projects may produce more polished lessons than failed projects, even though failures may be more informative.

The knowledge system should surface these risks rather than hide them.

---

## Example Knowledge Flow

A normal knowledge flow looks like this:

```text
Project completes
↓
Project outcome is recorded
↓
Static report is generated
↓
Knowledge curator drafts lesson and outcome notes
↓
Human reviews proposed knowledge
↓
Approved documents are committed to Git
↓
Future retrieval can use the documents
↓
Sabbatical review may later update or retire them
```

This flow keeps project evidence, semantic interpretation, and approval separate.

---

## Core Knowledge Scope

The knowledge system should support governed knowledge without overbuilding infrastructure.

The core knowledge system should support:

```text
Git-backed knowledge folder
manual markdown documents
basic front matter
simple document metadata registration
manual or rule-based retrieval
knowledge document references in scientist reviews
knowledge context section in reports
```

The core system includes a relational knowledge-graph projection. Vector search, automatic lesson approval, pull-request automation, automated contradiction detection, or a dedicated graph database require demonstrated value and explicit design.

A small reviewed knowledge layer is better than a large ungoverned memory system.

---

## Later Knowledge Abilities

Later versions may add:

```text
semantic search over knowledge documents
automatic proposal drafting
contradiction detection
stale-document detection
lesson confidence scoring
Git pull request automation
knowledge impact tracking
retrieval quality evaluation
sabbatical knowledge review
policy friction analysis
```

These abilities should be added only after the basic knowledge contracts are stable.

---

## Unsettled Questions

The first unsettled question is how strict the Git workflow should be in solo use versus team use.

The second unsettled question is how knowledge retrieval should evolve beyond inspectable rule-based retrieval while preserving provenance and evaluation.

The third unsettled question is when a hypothesis becomes a fact. This should require governance, not just repeated mention.

The fourth unsettled question is how to handle contradictory lessons. Contradictions should be surfaced rather than silently resolved.

The fifth unsettled question is how knowledge confidence should be represented. Evidence level, status, source projects, and production outcomes all matter.

The sixth unsettled question is how much knowledge context should be sent to an external scientist provider under privacy restrictions.

The seventh unsettled question is how to prevent a generated lesson from sounding more certain than the evidence supports.

---

## Out of Scope for This File

This file does not define the full database schema, scientist-provider prompts, report HTML layout, Git implementation details, approval workflow implementation, vector search architecture, or project lifecycle states.

Those belong in separate LASI documents.

This file defines how LASI manages semantic memory and institutional knowledge.
# Relationship to ICM

Git-backed knowledge remains the governed institutional knowledge layer. System
ICM is the selective operational context assembled for workers and may reference
knowledge documents, but it does not silently approve or promote facts, policies,
or lessons. Project findings remain project-scoped until a knowledge proposal is
reviewed under governance.
