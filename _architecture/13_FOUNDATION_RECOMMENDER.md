# 13_FOUNDATION_RECOMMENDER.md
# LASI Foundation Model Opportunity Recommender

## Purpose

This document defines how LASI identifies opportunities to train or prototype reusable foundation, self-supervised, or representation models from accumulated internal data.

The foundation recommender is responsible for scanning dataset portfolios, characterization records, experiment outcomes, project outcomes, repeated failure modes, unlabeled data volume, downstream task diversity, and semantic knowledge to determine whether a reusable model may be worth building.

It does not automatically train foundation models. It recommends opportunities, prototypes, validation plans, and approval paths.

The foundation recommender answers:

> Has LASI accumulated enough related data, repeated structure, and reusable task value to justify prototyping a reusable representation model?

---

## Core Idea

Most LASI projects should not start with foundation-model training.

Foundation-model work is expensive, uncertain, and easy to justify with vague arguments.

The foundation recommender exists to prevent both extremes:

```text
Never noticing when internal data has become valuable enough for representation learning.
Training expensive foundation models just because the idea sounds powerful.
```

The recommender should look for evidence that a reusable model would reduce future work, improve low-label performance, stabilize embeddings, improve clustering, or support multiple downstream tasks.

It should not recommend pretraining for one isolated dataset with one simple task and enough labels.

---

## Design Principles

### Reuse Before Pretraining

A foundation model is only worth considering if it can be reused.

The recommender should prioritize domains with many related datasets, recurring primitives, repeated failure modes, scarce labels, large unlabeled pools, and multiple downstream tasks.

If the benefit is limited to one project, a task-specific model is probably more appropriate.

---

### Evidence Before Ambition

Foundation-model recommendations must be evidence-driven.

The recommender should cite supporting evidence such as repeated dataset characterizations, repeated failure modes, repeated tool behavior, unlabeled data volume, low-label project failures, and downstream task overlap.

A recommendation should not be based only on the fact that foundation models are fashionable.

---

### Prototype Before Full Training

The default recommendation should be a prototype, not a full training program.

A prototype should use a limited data subset, constrained compute budget, explicit validation tasks, and clear success criteria.

Full training should require evidence from the prototype.

---

### Treat Representation Quality as a Hypothesis

A reusable encoder is only useful if its representations help real LASI workflows.

The recommender should evaluate representation quality through downstream tasks, clustering quality, retrieval quality, low-label performance, human-review usefulness, and similarity-bootstrap improvement.

It should not rely only on pretraining loss.

---

## Candidate Domains

The recommender should group possible foundation opportunities into candidate domains.

A candidate domain is a coherent family of related data and tasks.

Examples:

```text
wafer_defect_point_clouds
brightfield_defect_images
sem_defect_images
recipe_step_time_series
equipment_fault_sequences
wafer_map_patterns
```

A candidate domain should be broad enough for reuse but narrow enough that a shared representation may actually learn useful structure.

---

## Candidate Evidence

A foundation opportunity should be supported by evidence.

Relevant evidence includes:

```text
number of related dataset versions
number of related projects
amount of unlabeled data
amount of labeled data
number of downstream tasks
primitive recurrence
cluster structure recurrence
repeated failure modes
label scarcity
model families repeatedly relearning same features
tool usefulness patterns
human-review findings
dataset characterization similarity
deployment outcomes
cancelled projects caused by data scarcity
failed projects caused by representation weakness
```

Evidence should come from operational memory, artifact memory, outcome memory, and semantic memory.

---

## Data Signals

The recommender should look for data conditions that make foundation learning plausible.

Strong signals include:

```text
large unlabeled data pool
many related dataset versions
recurring primitives across datasets
multiple downstream tasks
similar geometry or texture across projects
scarce labels relative to raw data volume
repeated need for embeddings
repeated need for clustering
repeated low-label failures
```

Weak signals include:

```text
one dataset only
one narrow task only
enough labels for task-specific training
simple features already solve the problem
high label-policy instability
data too homogeneous
data too noisy to learn useful structure
no expected reuse
```

---

## Failure-Mode Signals

The recommender should look for repeated failure modes that suggest reusable representation learning may help.

Examples:

```text
small labeled datasets underperform across related tasks
embeddings are repeatedly generated from scratch
cluster analysis repeatedly finds similar primitives
models repeatedly relearn geometric features
task-specific models overfit quickly
unlabeled data is abundant but unused
manual review repeatedly needs similarity search
dataset similarity bootstrap is weak due to poor embeddings
```

Not every failure mode suggests foundation training.

If failures are caused by label ambiguity, unstable class definitions, bad benchmarks, or missing operational policy, pretraining may not help.

The recommender should explicitly identify when foundation training is unlikely to address the actual limiter.

---

## Opportunity Score

The foundation recommender should produce an opportunity score.

The score does not need to imply false precision. It should make reasoning explicit and auditable.

Suggested score components:

```text
Foundation Opportunity Score =
  data_volume_score
+ modality_reuse_score
+ primitive_recurrence_score
+ task_diversity_score
+ failure_recurrence_score
+ labeled_data_scarcity_score
+ expected_reuse_value
+ outcome_value_score
- compute_cost_penalty
- label_policy_instability_penalty
- narrow_domain_penalty
- privacy_constraint_penalty
- benchmark_weakness_penalty
```

The score should be accompanied by explanation.

A high score without explanation is not useful.

A medium score with clear evidence may be more actionable than a high score from a vague formula.

---

## Score Components

### Data Volume Score

Measures whether there is enough raw or unlabeled data to support representation learning.

The threshold depends on modality.

Point-cloud data, images, time series, and tabular data may have very different scale requirements.

### Modality Reuse Score

Measures whether the same modality appears across multiple projects.

A reusable encoder is more valuable when many projects use the same kind of data.

### Primitive Recurrence Score

Measures whether similar low-level structures recur.

For point-cloud scratch data, recurring primitives may include arcs, sparse clusters, dense clusters, line fragments, ring fragments, and curve segments.

### Task Diversity Score

Measures whether the representation can support multiple downstream tasks.

Examples include classification, retrieval, clustering, human-review ranking, anomaly detection, and dataset similarity.

### Failure Recurrence Score

Measures whether related projects repeatedly fail in ways a reusable representation might address.

### Labeled Data Scarcity Score

Measures whether labels are scarce, expensive, inconsistent, or slow to obtain.

Foundation learning is more attractive when unlabeled data is abundant and labels are limited.

### Expected Reuse Value

Measures expected future value.

A model that helps many future projects is more attractive than one that helps one current project.

### Outcome Value Score

Measures whether related projects have meaningful operational value.

A candidate domain tied to successful or high-value production outcomes may justify more investment than a purely exploratory domain.

### Compute Cost Penalty

Penalizes expensive training relative to expected value.

### Label Policy Instability Penalty

Penalizes domains where labels or class definitions are unstable.

Pretraining may help representation quality, but it does not solve unclear task definitions.

### Narrow Domain Penalty

Penalizes domains that are too narrow for reuse.

### Privacy Constraint Penalty

Penalizes domains where data cannot be pooled, moved, or used for pretraining under policy.

### Benchmark Weakness Penalty

Penalizes domains without reliable validation tasks.

A foundation prototype cannot be evaluated if the benchmark is weak.

---

## Opportunity Status

Foundation opportunities should have statuses.

Suggested statuses:

```text
candidate
needs_more_data
needs_better_benchmark
needs_label_policy_review
prototype_recommended
approved_for_prototype
prototype_running
prototype_successful
prototype_failed
approved_for_full_training
deferred
rejected
retired
```

Status should be updated as evidence changes.

A rejected opportunity may be revisited later if the dataset portfolio grows.

---

## Foundation Opportunity Report

The recommender should produce a structured report.

A report should include:

```text
opportunity_id
candidate_domain
candidate_modality
review_period
opportunity_score
recommendation
confidence
supporting_evidence
counter_evidence
data_summary
task_summary
failure_summary
outcome_summary
privacy_constraints
compute_estimate
prototype_plan
validation_tasks
success_criteria
risks
approval_required
```

The report should be saved as an artifact and referenced from the database.

It may also create a knowledge proposal or sabbatical review item.

---

## Prototype Plan

A foundation opportunity should usually produce a prototype plan, not a full training plan.

A prototype plan should define:

```text
training_data_scope
pretraining_objective
model_family
compute_budget
duration_limit
validation_tasks
baseline_comparison
success_criteria
failure_criteria
artifact_outputs
approval_required
```

Example:

```text
Train a small self-supervised point-cloud encoder on 250k unlabeled samples from three scratch-related dataset families. Evaluate frozen embeddings on scratch classification, rare-defect retrieval, and low-purity cluster separation. Continue only if low-label F1 improves by at least 3% and cluster purity improves in ambiguity regions.
```

---

## Validation Tasks

A foundation prototype must be evaluated on real tasks.

Possible validation tasks include:

```text
low-label classification
full-label classification
rare subclass retrieval
nearest-neighbor search
cluster purity improvement
human-review queue quality
dataset similarity bootstrap
outlier detection
domain-shift detection
few-shot transfer
```

Validation should compare against existing baselines.

A foundation model that improves pretraining loss but does not improve LASI workflows should not be promoted.

---

## Pretraining Objectives

The recommender may suggest pretraining objectives by modality.

For point clouds:

```text
masked point reconstruction
contrastive learning between augmented point clouds
cluster consistency learning
rotation or scale invariant prediction
local neighborhood reconstruction
geometry denoising
```

For images:

```text
masked image modeling
contrastive learning
DINO-style self-distillation
autoencoding
patch prediction
domain-specific augmentation consistency
```

For time series:

```text
masked timestep prediction
next-window prediction
contrastive temporal learning
anomaly-aware reconstruction
sequence denoising
```

These are candidates, not automatic choices.

The toolbox and scientist provider should help select appropriate objectives when a prototype is approved.

---

## Relationship to Dataset System

The foundation recommender depends heavily on the dataset system.

It uses dataset versions, dataset roles, dataset characterizations, primitive profiles, cluster profiles, quality profiles, coverage profiles, and benchmark status.

The recommender should not pool datasets that are not allowed to be pooled.

It should respect dataset roles such as:

```text
training
validation
test
frozen_benchmark
unlabeled_pretraining
synthetic
human_review
```

A dataset suitable for task training may not be suitable for foundation pretraining.

---

## Relationship to Memory System

The recommender uses memory to identify recurring opportunities.

It should retrieve:

```text
similar projects
repeated failure modes
tool usefulness records
recommendation outcomes
project outcomes
deployment outcomes
cancelled-project reasons
lessons
hypotheses
production failures
```

Memory prevents the recommender from considering only raw data volume.

A domain with smaller data but repeated high-value failures may be more important than a larger low-value domain.

---

## Relationship to Knowledge System

Foundation opportunities may create or use knowledge documents.

The recommender may use:

```text
facts about available data
policies about data movement
hypotheses about reusable primitives
lessons from prior projects
literature summaries
toolbox notes
diagnostic taxonomies
```

It may propose new knowledge documents, such as:

```text
hypothesis_foundation_encoder_for_pointcloud_defects.md
lesson_foundation_pretraining_low_value_for_unstable_labels.md
literature_summary_masked_point_modeling.md
```

It should not approve knowledge changes directly.

---

## Relationship to Sabbatical System

Foundation opportunity review may run as part of sabbatical review or as a separate scheduled workflow.

Sabbatical review may identify candidate domains.

The foundation recommender performs deeper opportunity scoring and prototype planning.

The two systems should exchange evidence but remain conceptually distinct.

Sabbatical review asks:

> What should the organization believe or change?

Foundation recommendation asks:

> Is reusable representation training worth prototyping?

---

## Relationship to Decision System

Foundation-model work is high-consequence.

The decision system should require approval for:

```text
foundation prototype training
full foundation training
pooling datasets across projects
using sensitive data for pretraining
changing dataset roles to unlabeled_pretraining
promoting foundation model to toolbox asset
```

The recommender may generate a proposal, but the decision system authorizes action.

---

## Relationship to Tool Registry

If a foundation model prototype succeeds, it may become a toolbox asset.

Example:

```text
tool_name: wafer_pointcloud_encoder_v1
tool_type: foundation_embedding_model
validated_on:
  - scratch_classification
  - rare_defect_retrieval
  - cluster_purity_analysis
introduced_in_toolbox_version: 0.8.0
```

The tool registry should record validation scope, known limitations, input requirements, and approved problem types.

A foundation model should not become a default tool until it has passed validation.

---

## Relationship to Reporting System

Static project reports may include a foundation opportunity section.

For projects without a foundation opportunity assessment, this section will be `deferred_to_later_phase`.

Later reports may show:

```text
whether the current dataset contributes to a foundation candidate pool
related dataset families
recurring primitives
unlabeled data volume
opportunity score
recommendation
prototype status
```

Foundation opportunity reports may be separate static artifacts.

---

## Relationship to Outcome System

Project outcomes should influence foundation opportunity scoring.

A domain with repeated successful deployments may justify investment because future improvements have operational value.

A domain with repeated failed production deployments may justify investment if failures are representation-related.

A domain with repeated cancellations due to unclear label policy may not be ready for foundation training.

The recommender should consider outcomes, not just experiment metrics.

---

## Relationship to Privacy Governance

Foundation pretraining may require pooling data.

Pooling data is a privacy and governance concern.

The recommender should identify privacy constraints early.

Questions include:

```text
Can data from multiple projects be pooled?
Can data leave its original environment?
Can unlabeled data be used for pretraining?
Can derived embeddings be stored?
Can sensitive metadata be included?
Can external providers train on this data?
```

If privacy constraints prevent useful pretraining, the opportunity should be marked blocked, deferred, or local-only.

---

## Opportunity Review Flow

A normal opportunity review flow is:

```text
Review is triggered
↓
Candidate domains are identified
↓
Dataset portfolio is queried
↓
Characterizations are summarized
↓
Unlabeled data volume is estimated
↓
Repeated primitives are identified
↓
Repeated failure modes are identified
↓
Project outcomes are reviewed
↓
Knowledge documents are retrieved
↓
Opportunity score is calculated
↓
Counter-evidence is identified
↓
Prototype plan is drafted
↓
Decision system evaluates approval requirement
↓
Foundation opportunity report is generated
```

---

## Prototype Execution Flow

A prototype execution flow is:

```text
Foundation opportunity proposal is approved
↓
Training data scope is frozen
↓
Pretraining objective is selected
↓
Remote execution plan is created
↓
Prototype model is trained
↓
Embeddings or model artifacts are produced
↓
Validation tasks are run
↓
Results are compared to baselines
↓
Prototype is marked successful, failed, or inconclusive
↓
Knowledge and toolbox proposals may be created
```

Prototype success should not automatically trigger full training.

---

## Core Foundation-Recommender Scope

The foundation recommender does not train foundation models.

The foundation recommender should preserve these design hooks:

```text
dataset roles that can identify unlabeled_pretraining data
dataset characterization records
project outcomes
tool usefulness records
knowledge hypotheses
foundation opportunity section in reports as deferred
```

A simple manual foundation opportunity note may be enough in early LASI.

The recommender should become active only after enough project and dataset history exists.

---

## Later Foundation Abilities

Later versions may add:

```text
scheduled opportunity scans
candidate-domain clustering
unlabeled data inventory
foundation opportunity scoring
prototype proposal generation
self-supervised training tools
representation evaluation suite
foundation model registry
toolbox promotion workflow
foundation model monitoring
foundation model retirement
```

These should be added only after dataset characterization, memory, outcomes, and governance are stable.

---

## Risks

The first risk is premature pretraining. Training a foundation model before the dataset portfolio is mature may waste compute.

The second risk is vague justification. “Foundation model” can become a label for expensive experimentation without clear expected value.

The third risk is poor validation. A foundation model may look good on pretraining loss but fail to improve real LASI workflows.

The fourth risk is label-policy confusion. Foundation models cannot fix unstable task definitions.

The fifth risk is privacy violation. Pooled pretraining may move data across boundaries that were acceptable for individual projects but not for combined training.

The sixth risk is hidden benchmark contamination. Pretraining may accidentally include benchmark data in a way that invalidates evaluation.

The seventh risk is operational lock-in. A foundation encoder may become widely used before its limitations are understood.

---

## Unsettled Questions

The first unsettled question is how much data is enough to justify a foundation prototype. The answer depends on modality and reuse value.

The second unsettled question is how to score representation quality. Downstream task performance, retrieval quality, cluster purity, and human-review utility may all matter.

The third unsettled question is whether foundation prototypes should train locally, through SSH, or on managed cloud infrastructure.

The fourth unsettled question is how to prevent benchmark leakage during pretraining.

The fifth unsettled question is how to handle proprietary data that cannot be pooled.

The sixth unsettled question is how to decide when a successful prototype becomes a toolbox asset.

The seventh unsettled question is how to retire or replace a foundation model when better representations become available.

---

## Out of Scope for This File

This file does not define foundation model architectures, training code, remote execution implementation, database schemas, benchmark construction details, or approval workflows.

Those belong in separate LASI documents.

This file defines how LASI identifies, evaluates, and proposes foundation-model opportunities.
