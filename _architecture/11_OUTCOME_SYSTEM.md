# 11_OUTCOME_SYSTEM.md

## Purpose

This document defines how LASI records, interprets, and uses project outcomes.

The outcome system is responsible for tracking what ultimately happened after experiments were run. It records whether a project was deployed, validated but not deployed, cancelled, abandoned, blocked, superseded, failed validation, failed in production, successful in production, or closed as research-only.

It does not define model training, deployment infrastructure, database schemas, report templates, or governance rules in detail. Those belong in separate LASI documents.

The outcome system answers:

> What happened to this project after experimentation, and how should that outcome influence future LASI decisions?

---

## Core Idea

A LASI project is not complete when experiments finish.

A project is complete when its outcome is recorded.

Benchmark evaluation is offline evidence only. A successful hidden-label score may support `validated_not_deployed`, but never implies `deployed` or `successful_in_production`. Benchmark failures and blocked evaluations remain outcome evidence and may produce draft knowledge proposals.

A model that performs well in validation but is never deployed is not the same as a model that succeeds in production.

A model that succeeds in validation but fails in production is not a success.

A project that is cancelled because labels are unstable may still produce valuable knowledge.

The outcome system prevents LASI from confusing experimental success with operational value.

---

## Design Principles

### Outcomes Are First-Class Records

Project outcomes should be stored as first-class records, not buried in notes.

The system should be able to query outcomes across projects.

Examples:

```text
Show all projects that validated but were not deployed.
Show all deployed models that later failed in production.
Show all cancelled projects caused by label-policy instability.
Show all projects blocked by privacy restrictions.
```

Outcome memory helps LASI learn which recommendations produced durable value.

---

### Outcome Notes Matter

Structured outcome statuses are necessary but not sufficient.

The system also needs narrative notes explaining why a project ended the way it did.

For example, `validated_not_deployed` is too vague by itself. The project may not have deployed because the data feed was unavailable, the model was too slow, the business no longer needed it, or the production owner rejected the failure modes.

The status should be searchable.

The notes should explain reality.

---

### Outcomes Can Change Over Time

A project can move from `deployed` to `failed_in_production`.

A project can move from `validated_not_deployed` to `deployed` months later.

A cancelled project can later be revived.

Therefore, outcomes should be event-based or append-only where possible.

The system should preserve outcome history rather than overwriting it.

---

### Outcomes Influence Memory

Outcomes should affect future recommendations.

A tool or architecture that produced validation success but repeated production failure should be treated with caution.

A dataset characterization pattern that led to successful production deployments should receive more weight than a pattern seen only in offline validation.

A cancelled project may still teach LASI something important.

---

## Outcome Statuses

LASI should use a controlled set of outcome statuses.

Suggested statuses:

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

### Pending

The project has not yet reached a final outcome.

This is common immediately after report generation.

### Research Only

The project was exploratory and was never intended for deployment.

This can still produce lessons and useful tooling.

### Validated Not Deployed

The project produced a model, method, or result that passed offline validation but was not deployed.

The reason should be recorded.

### Deployed

The model or process was placed into some production or operational workflow.

Deployment does not imply success. It only means the system entered operational use.

### Successful in Production

The deployed model or process achieved its intended operational value.

This should require evidence, not just deployment.

### Failed Validation

The project did not meet validation requirements.

This is different from cancellation. A failed-validation project attempted to meet criteria and did not.

### Failed in Production

The project passed some prior gate but failed after deployment.

Failure may be due to domain shift, data feed issues, latency, poor monitoring, unacceptable false positives, unacceptable false negatives, human rejection, or operational mismatch.

### Cancelled

The project was intentionally stopped before completion.

Cancellation may be due to business priority, unstable labels, data unavailability, budget constraints, privacy constraints, tool gaps, or lack of expected value.

### Abandoned

The project stopped without a clear formal decision.

This is less desirable than cancelled because the reason may be unclear.

### Blocked

The project cannot proceed because a dependency, approval, dataset, tool, privacy clearance, or compute resource is unavailable.

### Superseded

The project was replaced by another project, dataset, model, method, or operational approach.

### Archived

The project is retained for history but is no longer active.

---

## Outcome Events

Outcome history should be recorded as events.

An outcome event should include:

```text
event_id
project_id
previous_status
new_status
reason
evidence
owner
created_at
related_report_id
related_experiment_id
related_deployment_id
notes
```

Event-based outcomes preserve history.

Example:

```text
2026-05-29: project marked deployed
2026-06-18: project marked failed_in_production due to high false positives on Tool B
2026-06-20: knowledge proposal created to update deployment guidance
```

This is better than overwriting `deployed` with `failed_in_production` and losing the timeline.

---

## Outcome Record

A project should also have a current outcome record.

The current record summarizes the latest state.

It should include:

```text
project_id
current_status
final_disposition
deployment_status
production_status
result_summary
cancellation_reason
failure_reason
blocked_reason
owner
decision_date
last_updated_at
related_reports
related_artifacts
follow_up_actions
```

The current record is useful for quick queries.

The event log is useful for history.

---

## Outcome Reasons

Outcome reasons should be controlled enough for search but flexible enough for reality.

Suggested reason categories:

```text
met_success_criteria
failed_metric_threshold
failed_operational_requirement
failed_latency_requirement
failed_reliability_requirement
failed_human_review
failed_production_monitoring
domain_shift
data_feed_unavailable
data_quality_insufficient
label_policy_unstable
privacy_block
approval_block
budget_exhausted
tool_unavailable
compute_unavailable
business_priority_changed
superseded_by_better_solution
research_goal_completed
unknown
```

Outcome notes should provide narrative detail.

---

## Deployment Outcome

If a project is deployed, LASI should eventually record deployment outcome.

Deployment outcome should include:

```text
deployment_date
deployment_owner
deployment_environment
model_or_method_version
dataset_version_used
monitoring_plan
rollback_plan
success_criteria
observed_performance
production_issues
final_production_status
```

This does not mean LASI must manage deployment infrastructure.

It means LASI should record what happened after deployment.

---

## Production Failure

Production failure should be treated as high-value evidence.

A production failure may reveal problems that validation did not capture.

Possible production failure causes include:

```text
domain_shift
data_pipeline_change
unexpected input distribution
label policy mismatch
human workflow rejection
latency too high
false positives too costly
false negatives too costly
monitoring insufficient
model drift
tool integration failure
operational owner rejected output
```

A production failure should trigger review of related lessons, policies, datasets, benchmarks, and similarity priors.

The system should ask:

> What did validation fail to reveal?

---

## Validated but Not Deployed

Validated-but-not-deployed projects are important.

They may indicate:

```text
technical success but no operational path
missing production data feed
lack of owner
privacy restriction
integration cost too high
model not trusted by users
business priority changed
insufficient explainability
deployment tooling unavailable
```

These projects should not be counted as production successes.

They may still produce useful research lessons.

---

## Cancelled Projects

Cancelled projects should be recorded carefully.

Cancellation is not necessarily failure.

A cancelled project may be one of the most valuable outcomes if it prevents wasted effort.

Examples:

```text
cancelled because label policy was unstable
cancelled because dataset coverage was insufficient
cancelled because privacy policy blocked necessary evidence
cancelled because expected value became too low
cancelled because a simpler rule-based solution was sufficient
```

The cancellation reason should influence future memory.

---

## Outcome and Scientist Reviews

Scientist reviews should eventually be evaluated against outcomes.

If a scientist provider recommended a path that led to production success, that recommendation pattern becomes stronger evidence.

If a scientist provider recommended a path that repeatedly led to failed production outcomes, that pattern should be downgraded.

Outcome records can help calibrate scientist-provider confidence.

Example:

```text
Scientist diagnosis:
data_coverage, confidence 0.78

Outcome:
dataset update was deployed and successful in production

Interpretation:
diagnosis likely confirmed
```

or:

```text
Scientist diagnosis:
model_capacity, confidence 0.82

Outcome:
larger model validated offline but failed in production due to false positives

Interpretation:
diagnosis incomplete; threshold policy or operational cost was underweighted
```

---

## Outcome and Experiment Memory

Experiment memory should treat project outcome as a quality signal.

A model configuration that produced strong validation metrics but failed in production should not be treated as a historical best approach without caveats.

A tool that revealed a fatal issue before deployment may be high-value even if the project was cancelled.

A dataset update that improved validation but did not change production outcome should be evaluated carefully.

Outcome memory adds operational meaning to experiment memory.

---

## Outcome and Similarity Bootstrap

Similarity bootstrap should include outcomes.

When LASI retrieves similar prior projects, it should consider:

```text
Was the prior project deployed?
Did it succeed in production?
Was it cancelled?
Did it fail validation?
Did it fail in production?
Was it research-only?
Was the outcome caused by model behavior, data quality, policy, or operations?
```

A prior method that succeeded in production should carry more weight than one that only improved validation.

A prior method that failed in production should be retrieved as cautionary evidence.

---

## Outcome and Knowledge Layer

Outcome records may generate knowledge proposals.

Examples:

```text
A failed production deployment may trigger a lesson about domain shift.

A cancelled project may trigger a policy proposal requiring label-policy review before model sweeps.

A successful deployment may strengthen a hypothesis about a useful architecture or diagnostic.

A validated-not-deployed project may create a lesson about deployment readiness.
```

The knowledge curator may draft lessons or retrospectives from outcomes.

Humans approve knowledge updates.

---

## Outcome and Reports

Static reports should include current outcome status.

If outcome is pending, the report should say so.

If a project outcome is recorded later, LASI may generate an outcome addendum or deployment retrospective.

The original diagnostic report should remain immutable if it was used for review or decision-making.

Outcome documents may reference the original report.

---

## Outcome Documents

Outcome records should be structured in the database, but narrative outcome documents may be stored as markdown.

A project may generate:

```text
projects/
└── project_id/
    ├── report.html
    ├── executive_summary.md
    ├── outcome.md
    ├── lessons.md
    └── deployment_review.md
```

The database stores searchable status.

The markdown documents explain context.

This combines operational memory with semantic memory.

---

## Outcome Review

Some outcomes should require review.

Examples:

```text
failed_in_production
successful_in_production
promote_to_production_success_pattern
production_failure_affects_policy
deployment_failure_invalidates_prior_lesson
```

High-consequence outcomes may affect institutional knowledge and should not be applied silently.

---

## Outcome Data Flow

A normal outcome flow is:

```text
Project reaches decision point
↓
Current outcome status is recorded
↓
Outcome event is appended
↓
Report is generated or updated
↓
If appropriate, outcome document is drafted
↓
Knowledge curator may propose lessons
↓
Future memory retrieval uses outcome status
```

For deployed projects, a later flow may occur:

```text
Production evidence arrives
↓
Outcome event updates status
↓
Deployment review is drafted
↓
Related lessons and hypotheses are checked
↓
Knowledge proposals may be created
```

---

## Relationship to Decision System

The decision system may set or recommend outcome status.

Examples:

```text
stop_project → cancelled or research_only
blocked_by_privacy → blocked
stop_low_expected_value → cancelled or research_only
deployment_approved → deployed
validation_failed → failed_validation
```

Some outcomes may require human confirmation.

The decision system should not mark `successful_in_production` without evidence.

---

## Relationship to Reporting System

The reporting system displays outcome status.

Reports should show whether the project is pending, closed, deployed, failed, cancelled, or blocked.

Outcome status should help readers interpret experiment results.

A validation result from a project that later failed in production should not be read the same way as a validation result from a production success.

---

## Relationship to Memory System

Outcome memory improves future recommendations.

The memory system should use outcome status when ranking prior examples.

Production-confirmed results should be weighted differently from validation-only results.

Failed production results should be used as cautionary context.

Cancelled projects should be searchable by cancellation reason.

---

## Relationship to Knowledge System

Outcome narratives and deployment retrospectives may become semantic memory.

The knowledge system should store reviewed lessons from outcomes.

For example:

```text
Policy:
Projects with unstable label policy should not proceed to architecture sweeps.

Source:
Multiple cancelled projects and one failed production deployment.
```

The outcome system provides evidence. The knowledge system stores reviewed institutional interpretation.

---

## MVP Outcome Scope

The MVP should support:

```text
current outcome status
append-only outcome events
outcome notes
basic outcome reasons
pending outcome by default
outcome section in static report
OpenCode command or outcome-recording skill to set or update outcome
outcome references in project records
```

The MVP does not need deployment monitoring integration, automated production metrics ingestion, role-based outcome approval, or advanced retrospective generation.

A simple outcome ledger is enough to prevent LASI from losing what happened after experiments.

---

## Later Outcome Abilities

Later versions may add:

```text
deployment review templates
production monitoring integration
automatic outcome reminders
outcome-based scientist calibration
deployment-success weighting in similarity bootstrap
production-failure contradiction detection
outcome dashboards
project retrospective generation
knowledge proposal automation
```

These should be added after basic outcome recording is stable.

---

## Unsettled Questions

The first unsettled question is who is allowed to set or change project outcome status. Solo use may allow the operator; team use may require project owner or production owner approval.

The second unsettled question is how much evidence is required for `successful_in_production`.

The third unsettled question is how to distinguish `cancelled`, `abandoned`, and `blocked` in practice.

The fourth unsettled question is how often deployed projects should be revisited for outcome updates.

The fifth unsettled question is whether outcome statuses should be immutable events only or also stored as current-state fields. The likely answer is both.

The sixth unsettled question is how production failure should affect existing knowledge. A single failure may not invalidate a lesson, but it should trigger review.

The seventh unsettled question is whether validated-but-not-deployed should count as success, partial success, or unresolved. The answer depends on project intent.

---

## Out of Scope for This File

This file does not define deployment infrastructure, production monitoring implementation, database schemas, report HTML layout, role-based access control, or knowledge approval workflows.

Those belong in separate LASI documents.

This file defines how LASI records and uses project outcomes.
