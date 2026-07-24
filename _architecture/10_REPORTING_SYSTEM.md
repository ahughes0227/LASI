# 10_REPORTING_SYSTEM.md
# LASI Reporting System

## Purpose

This document defines how LASI generates, stores, and uses reports.

The reporting system is responsible for producing fixed-template static HTML reports that communicate what was tested, what was learned, what appears to limit performance, what action is recommended, what decision was made, and what outcome status the project currently has.

It does not define model training, dataset storage, database schemas, scientist-provider prompts, or human approval workflows in detail. Those belong in separate LASI documents.

The reporting system answers:

> What did LASI learn, what evidence supports it, what should happen next, and how can a human audit the conclusion?

---

## Core Idea

The report is the primary human-facing artifact of a LASI project.

The report is not a freeform LLM essay.

It is a fixed-template static webpage generated from structured data.

The report should be readable by engineers, domain experts, reviewers, and future agents. It should summarize the project clearly while preserving enough provenance to audit the conclusion.

The report should help a human answer:

```text
What dataset was used?
What experiments were run?
What models or tools were compared?
What failed?
What worked?
What is probably limiting performance?
What evidence supports that diagnosis?
What action is recommended?
Was the recommendation allowed, blocked, or escalated?
Is more experimentation worthwhile?
What is the current project outcome?
```

---

## Design Principles

### Fixed Template

Reports should use a fixed layout.

The scientist provider may populate specific fields and summaries, but it should not invent new report sections dynamically.

This keeps reports comparable across projects and prevents important sections from disappearing when a model omits them.

---

### Static Output

Reports should be static HTML.

The MVP should not require a running web server, database connection, or application backend to view a report.

A report should be reviewable offline if the artifact bundle is available.

---

### Structured Data First

The report generator should consume a typed `StaticReportData` object.

The report should not be generated directly from unstructured logs or raw model output.

The pipeline should look like:

```text
Operational records
+ MLflow artifacts
+ scientist review
+ local decision
+ project outcome
+ knowledge references
↓
StaticReportData
↓
Fixed HTML template
↓
report.html + assets
```

---

### Missing Data Must Be Visible

Every required section should render even when data is missing.

Missing data should be explicit.

Allowed missing-data labels include:

```text
not_run
not_available
not_applicable
blocked_by_privacy
blocked_by_policy
deferred_to_later_phase
failed
partial_success
```

The report should never look complete when an analysis was skipped.

---

### Claims Need Provenance

Important claims should trace back to evidence.

A claim may reference a metric, dataset characterization, experiment run, scientist review, decision record, knowledge document, human review, or project outcome.

Reports should distinguish:

```text
observed evidence
model inference
scientist-provider recommendation
decision-system outcome
human feedback
approved knowledge
tentative knowledge
```

This prevents the report from blending facts, hypotheses, and recommendations.

---

## Report Artifact Model

The preferred MVP artifact structure is:

```text
reports/
└── project_id/
    ├── report.html
    ├── assets/
    │   ├── style.css
    │   ├── confusion_matrix.png
    │   ├── learning_curve.png
    │   ├── latent_space.png
    │   └── sample_grids/
    ├── report_data.json
    └── report_manifest.yaml
```

The report should be logged to MLflow or the artifact store.

The database should store a report record that points to the artifact URI.

For small reports, a self-contained HTML file with embedded assets may be acceptable. For larger reports, HTML plus an assets directory is more maintainable.

---

## StaticReportData

`StaticReportData` is the structured object passed into the report template.

It should include all required report sections.

Suggested top-level fields:

```text
report_header
executive_summary
current_decision
dataset_summary
dataset_characterization
dataset_portfolio_status
experiment_summary
model_comparison
performance_gap_diagnosis
learning_curves
error_analysis
latent_or_cluster_analysis
representative_samples
scientist_review
decision_record
knowledge_context
memory_context
recommendation
project_outcome
lessons_captured
foundation_opportunity
appendix
```

A section may be populated, not run, blocked, failed, or not applicable.

The report template should render each state consistently.

---

## Report Header

The report header identifies the project and run context.

It should include:

```text
project_id
project_name
problem_type
modality
dataset_id
dataset_version
report_generated_at
harness_version
toolbox_version
scientist_provider_profile
privacy_mode
execution_backends_used
```

The header should make it clear which dataset version and system configuration produced the report.

---

## Executive Summary

The executive summary is the fast-read section.

It should be understandable in less than a minute.

It should include:

```text
best_current_result
primary_diagnosis
diagnosis_confidence
recommended_next_action
decision_status
project_outcome_status
one_sentence_rationale
```

The executive summary should not bury uncertainty.

If the diagnosis is weak, the summary should say so.

---

## Current Decision

This section describes what LASI decided after reviewing the scientist recommendation.

Possible decision outcomes include:

```text
allow
allow_with_warning
block
escalate_for_approval
convert_to_proposal
request_clarification
stop_project
defer
```

This section should include the reason for the decision and any required human action.

Example:

```text
Decision:
Escalate for approval.

Reason:
The scientist provider recommended creating a new dataset version by correcting labels in Cluster 12. Label changes require human approval under the active governance policy.
```

---

## Dataset Summary

The dataset summary identifies the dataset version used in the report.

It should include:

```text
dataset_id
dataset_version
dataset_role
sample_count
label_schema
class_balance
parent_version
change_type
comparability_status
benchmark_status
```

This section should make it impossible to confuse results from one dataset version with another.

---

## Dataset Characterization Section

This section summarizes the dataset characterization.

It should include:

```text
primitive_profile
distribution_profile
cluster_profile
quality_profile
coverage_profile
separability_profile
ambiguity_profile
parent_version_comparison
dataset_risks
```

The report should emphasize dataset findings that affect experiment interpretation.

For example, low-purity clusters, label ambiguity, severe imbalance, duplicate samples, or coverage gaps should be visible in this section.

---

## Dataset Portfolio Status

This section appears when dataset portfolio data exists.

It should show how the current dataset version fits into lineage.

It may include:

```text
parent_version
child_versions
change_reason
dataset_improvement_proposals
comparability_notes
benchmark_role
dataset_status
```

This section helps reviewers understand whether a performance change is due to model behavior, dataset change, benchmark change, or label-policy change.

---

## Experiment Summary

The experiment summary describes what was run.

It should include:

```text
experiment_ids
experiment_types
tool_runs
execution_backends
remote_hosts_used
success_count
failure_count
partial_success_count
total_runtime
major_warnings
```

It should not attempt to interpret everything. Interpretation belongs in later sections.

---

## Model Comparison

The model comparison section compares relevant model or tool outputs.

For model experiments, it may include:

```text
model_family
model_config
dataset_version
train_metric
validation_metric
test_metric
generalization_gap
runtime
artifact_links
notes
```

The table should show whether results are directly comparable, partially comparable, or not comparable.

A model should not be called “better” if the comparison is not valid.

---

## Performance Gap Diagnosis

This section is the core diagnostic interpretation.

It should identify suspected performance limiters.

Suggested fields:

```text
limiter_type
confidence
supporting_evidence
counter_evidence
recommended_test
status
```

Limiter types should use the diagnostic taxonomy.

Examples include:

```text
label_ambiguity
data_coverage
model_capacity
representation_gap
preprocessing_issue
domain_shift
threshold_policy
benchmark_leakage
```

This section should clearly separate observed facts from inferred diagnosis.

---

## Learning Curves

This section shows learning-curve and scaling-test results if available.

It may include:

```text
training_curve
validation_curve
dataset_size_scaling
model_size_scaling
training_duration_scaling
interpretation
```

If no learning curve was run, the section should say `not_run`.

If learning curves were blocked due to budget, the section should say `blocked_by_policy` or `blocked_by_budget`.

---

## Error Analysis

This section summarizes failure behavior.

It should include:

```text
confusion_matrix
top_confused_classes
false_positive_summary
false_negative_summary
high_confidence_wrong_samples
low_confidence_borderline_samples
error_buckets
recommended_review_targets
```

For industrial ML, this section is often more important than aggregate metrics.

---

## Latent or Cluster Analysis

This section summarizes embedding, clustering, or latent-space analysis.

It may include:

```text
embedding_method
cluster_method
cluster_count
noise_fraction
cluster_purity
low_purity_clusters
class_overlap_score
hidden_subclass_candidates
representative_clusters
```

This section should help explain whether failures are random or concentrated in meaningful regions.

---

## Representative Samples

This section displays examples when privacy policy allows.

Possible categories:

```text
true_positives
true_negatives
false_positives
false_negatives
borderline_samples
high_confidence_wrong_samples
low_purity_cluster_representatives
human_review_candidates
```

Each sample card should include sample ID, true label, predicted label, confidence if available, cluster ID if available, reason selected, and artifact link.

If samples cannot be shown due to privacy, the section should explicitly say so.

---

## Scientist Review Section

This section shows the normalized scientist review.

It should include:

```text
provider_profile
model_name
review_timestamp
primary_diagnosis
confidence
supporting_evidence
counter_evidence
alternative_hypotheses
recommended_next_action
expected_value
estimated_cost
stop_recommendation
knowledge_documents_used
```

This section should not present the scientist provider as unquestionable authority.

It should be clear that this is a recommendation reviewed by the decision system.

---

## Decision Record Section

This section shows how the decision system handled the recommendation.

It should include:

```text
recommendation
decision
risk_level
policy_checks
privacy_checks
budget_checks
tool_availability_checks
comparability_checks
approval_required
blocked_reason
next_required_action
```

This is one of the most important audit sections.

It explains why LASI did or did not execute the recommended action.

---

## Knowledge Context Section

This section lists relevant knowledge documents used in the review.

It should include:

```text
document_id
title
type
status
evidence_level
path
git_commit
reason_included
```

The report should distinguish approved policies from tentative lessons and active hypotheses.

This prevents hidden retrieval from influencing recommendations without visibility.

---

## Prior Memory Context

This section summarizes similar prior projects or dataset versions.

It may include:

```text
similar_project_id
similar_dataset_version
similarity_reason
historical_best_action
historical_outcome
deployment_status
cautionary_notes
```

This section supports similarity bootstrap and helps future readers understand whether LASI has seen similar cases.

---

## Recommendation and Next Action

This section states the recommended next action in operational terms.

It should include:

```text
next_action
owner
required_inputs
expected_value
estimated_cost
success_criteria
failure_criteria
approval_required
fallback
```

The recommendation should be actionable.

Bad:

```text
Improve the dataset.
```

Better:

```text
Create a human review queue of 150 samples from low-purity Cluster 12 to determine whether short low-point-count arcs should be labeled scratch or non_scratch.
```

---

## Project Outcome Section

This section records the current project outcome status.

Possible statuses include:

```text
pending
research_only
validated_not_deployed
deployed
cancelled
abandoned
superseded
failed_validation
failed_in_production
successful_in_production
blocked
```

The report should show outcome notes if available.

A project may have useful diagnostic results even if it is never deployed.

Outcome status helps future memory retrieval avoid treating all validation successes as operational successes.

---

## Lessons Captured

This section records candidate lessons from the project.

Lessons may be:

```text
not_captured
draft
tentative
approved
contradicted
retired
```

The report should distinguish between a lesson drafted by the system and a lesson approved into institutional knowledge.

Example:

```text
Draft Lesson:
In this dataset, short low-point-count arcs were the dominant source of label ambiguity.

Status:
Draft only. Requires human review before entering the knowledge layer.
```

---

## Foundation Opportunity Section

This section appears only when foundation-model opportunity analysis exists.

It may include:

```text
candidate_domain
candidate_modality
opportunity_score
supporting_evidence
unlabeled_data_volume
recurring_primitives
downstream_tasks
recommended_prototype
```

For MVP reports, this section should render as `deferred_to_later_phase`.

---

## Appendix

The appendix preserves audit and debugging detail.

It may include:

```text
full metric tables
full tool run list
config snapshot
dataset manifest reference
environment summary
remote execution details
MLflow run IDs
artifact URIs
raw scientist review artifact
decision logs
warnings
failures
schema versions
```

The appendix does not need to be beautiful. It needs to be complete enough for audit.

---

## Report Provenance

Reports should preserve provenance.

A report should record:

```text
report_id
project_id
dataset_version
generated_at
harness_version
template_version
report_schema_version
source_records
source_artifacts
scientist_review_id
decision_id
knowledge_document_refs
mlflow_run_refs
```

If a report is regenerated, LASI should preserve the difference between the original report and the regenerated report.

Reports used for review or signoff should be treated as immutable artifacts.

---

## Report States

A report may have states.

Suggested states:

```text
draft
generated
reviewed
accepted
rejected
superseded
archived
```

The MVP may only need `generated`, but later systems may require review and signoff.

---

## Handling Missing Sections

Each section should support a standard status.

Suggested section statuses:

```text
complete
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

The report renderer should display section status consistently.

Missing information should not silently disappear.

---

## Report Styling

Report styling should prioritize clarity over visual complexity.

The report should be readable in a browser without a backend.

It should use stable layout, clear section headings, tables for comparisons, plots for diagnostics, and explicit warnings for missing or blocked data.

The MVP should avoid complex frontend frameworks.

A simple Jinja2 template plus CSS is sufficient.

---

## Report Generation Flow

A normal report generation flow is:

```text
Project state is loaded
↓
Relevant database records are retrieved
↓
MLflow artifact references are resolved
↓
Scientist review is loaded
↓
Decision record is loaded
↓
Knowledge context is loaded
↓
Project outcome is loaded
↓
StaticReportData is assembled
↓
Template renders report.html
↓
Assets are copied or linked
↓
Report is logged as artifact
↓
Report record is stored in database
```

Report generation should be repeatable from stored records and artifacts.

---

## Report and Privacy

The report must respect privacy policy.

If representative samples, labels, metadata, or raw data cannot be shown, the report should state that the section was blocked by privacy.

If a report is intended for broader sharing, it may need a redacted version.

Possible report visibility levels:

```text
internal_full
internal_redacted
external_summary
local_only
```

The MVP may only need internal/local reports, but privacy-aware design should start early.

---

## Report and Knowledge Layer

Reports may generate candidate knowledge.

A report may include draft lessons, open hypotheses, and recommended knowledge updates.

However, reports do not directly update institutional knowledge.

The knowledge curator may use report contents to draft knowledge proposals.

Human approval is required for high-consequence knowledge changes.

---

## Report and Project Outcome

Reports should show current project outcome.

A project outcome may be pending when the report is generated.

Later, if the project is deployed, cancelled, or fails in production, a new outcome note or retrospective may be created.

The original report should remain as a historical artifact.

Later outcome documents can reference the report.

---

## MVP Reporting Scope

The MVP report should include:

```text
header
executive_summary
current_decision
dataset_summary
dataset_characterization
experiment_summary
model_comparison
performance_gap_diagnosis
error_analysis
scientist_review
decision_record
recommendation
project_outcome_status
appendix
```

The MVP report does not need polished interactivity, advanced filtering, dynamic dashboards, role-based views, or a GUI.

The goal is a reliable static engineering review packet.

---

## Later Reporting Abilities

Later versions may add:

```text
redacted report variants
report signoff workflow
interactive local-only visualizations
comparison across reports
dataset portfolio report
sabbatical report
foundation opportunity report
knowledge impact report
deployment retrospective report
automated executive summary export
```

These should be added after the fixed static report contract is stable.

---

## Unsettled Questions

The first unsettled question is the exact report wireframe. The section list is known, but the visual hierarchy needs a concrete golden example.

The second unsettled question is how much prose should come from the scientist provider versus deterministic templates.

The third unsettled question is how to handle report regeneration. The system should preserve original reports used for decisions.

The fourth unsettled question is how much raw sample display is allowed under privacy constraints.

The fifth unsettled question is whether reports need formal signoff in the MVP.

The sixth unsettled question is whether reports should be single-file HTML or HTML plus assets. HTML plus assets is better for large reports; single-file HTML is easier to share.

The seventh unsettled question is how much report content should be redacted for external review.

---

## Out of Scope for This File

This file does not define the full HTML template, CSS, database schema, report-rendering code, scientist-provider prompt, or human signoff workflow.

Those belong in separate LASI documents.

This file defines how LASI thinks about reports as static, structured, auditable engineering review artifacts.
