# 08_DECISION_SYSTEM.md

## Purpose

This document defines how LASI decides whether a recommended action may proceed.

The decision system is responsible for authorization, blocking, escalation, stop/go logic, approval requirements, budget checks, privacy checks, risk classification, and policy enforcement.

It does not generate scientific recommendations. It evaluates recommendations.

The decision system answers:

> Given the current project state, recommendation, evidence, policy, budget, and risk, is this action allowed?

## Administrator and Runner Boundary

The OpenCode administrator controls assignment lifecycle but does not authorize research actions. `ProjectRunner` schedules coordinator turns but cannot bypass decisions. Each proposed experiment still becomes an `ExperimentPlan` and passes the decision system. Routine allowed work continues without conversational permission; escalation is reserved for genuine human discretion or a high-consequence boundary.

---

## Core Idea

The scientist provider recommends.

The experiment planner translates.

The decision system authorizes.

The tool registry constrains.

Humans approve high-consequence changes.

This separation is essential. A recommendation may be scientifically reasonable but operationally forbidden. A tool may exist but be unavailable under the current privacy policy. A proposed experiment may be useful but over budget. A dataset change may be beneficial but require human approval.

The decision system prevents LASI from becoming an uncontrolled autonomous agent.

For locally supplied benchmark challenges, execution also requires a verified benchmark-isolation profile. Approval of a plan does not override unavailable technical containment. Network, external-provider, remote-execution, arbitrary-subprocess, hidden-label, and path-allowlist violations are blocked and recorded as operational evidence.

---

## Design Principles

### Assignment Autonomy Is Not Repeated Human Approval

The assignment defines the objective and operating scope. Inside that scope, the
decision system evaluates every experiment plan deterministically and records
the result. An `allow` decision continues the research loop automatically; it is
not surfaced as a request for user authorization. This applies to local work and
to work on an already-approved remote host when privacy, transfer, trust, tool,
and budget checks pass.

Human discretion is requested only when the next useful action changes scope or
crosses a governed boundary: dataset or label meaning, benchmark definition,
privacy posture, unapproved data movement or host use, budget expansion,
toolbox/knowledge promotion, deployment, policy conflict, or another explicitly
high-consequence action. If such an action is useful but not essential, LASI
records a proposal and continues exploring safe alternatives instead of pausing.

Recoverable tool failure, partial success, scientific uncertainty, a weak score,
or a rejected near-duplicate hypothesis is not a human blocker. These outcomes
route back through exploration and review. Performance stopping requires the
research-loop plateau evidence defined by the experiment system.

A missing component is also not automatically a human blocker. The coordinator
routes a typed request to the component reviewer. A durable automatic review may
authorize project-scoped experimental registration when deterministic security,
containment, dependency, interface, test, resource, and stability checks pass.
Correctable deficiencies route to revision. Human escalation is reserved for a
genuine boundary risk or shared toolbox promotion.

### Recommendations Are Not Commands

A recommendation is an input to the decision system.

It is not permission to execute.

A scientist provider may recommend a larger model, human review, dataset update, label-policy change, knowledge update, or project stop. The decision system determines whether the action is allowed, blocked, escalated, or converted into a proposal.

---

### High-Consequence Actions Require Approval

Some actions can materially alter the project, dataset, knowledge base, benchmark, or production behavior. These require explicit approval.

Examples include modifying labels, creating dataset versions, changing benchmarks, sending raw data to an external provider, changing policies, promoting hypotheses to facts, deploying models, or launching expensive training.

---

### Stop Is a Valid Decision

Stopping is not failure.

A project may stop because the next action is low value, labels are ambiguous, the dataset is insufficient, privacy blocks the needed evidence, the budget is exhausted, or human review is required.

LASI should record why it stopped.

A well-supported stop decision is a successful diagnostic outcome.

---

### Decisions Must Be Traceable

Every decision should preserve:

```text
recommendation_id
decision_id
project_id
decision
reason
policy_checks
budget_checks
privacy_checks
risk_level
approval_required
approved_by
created_at
```

Future reviewers should be able to see why an action was allowed or blocked.

---

## Decision Types

The decision system should support a controlled set of decision outcomes.

Suggested decisions:

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

### Allow

The recommendation is permitted and may be executed.

### Allow With Warning

The recommendation is permitted, but the system records a warning. This may apply when cost is near the limit, evidence is weak, or a prior similar action had mixed results.

### Block

The recommendation is not permitted.

Blocking may occur because of privacy, budget, unavailable tools, invalid action type, missing evidence, duplicate work, non-comparable data, or policy violation.

### Escalate for Approval

The recommendation may be reasonable but requires human approval.

### Convert to Proposal

The recommendation should not execute directly but should become a proposal.

Examples include dataset improvement proposals, knowledge proposals, toolbox change proposals, or deployment proposals.

### Request Clarification

The recommendation is too vague, malformed, unsupported, or missing required information.

### Stop Project

The system recommends stopping the current experimental path or closing the project with an outcome status.

### Defer

The decision is postponed because a dependency is missing, a review is pending, or a required artifact is unavailable.

---

## Action Risk Levels

Actions should be classified by risk.

Suggested risk levels:

```text
low
medium
high
critical
```

### Low Risk

Low-risk actions are reversible or informational.

Examples:

```text
generate report
run small local characterization
run small baseline probe within budget
query database
retrieve approved knowledge documents
render plots
```

Low-risk actions may be allowed automatically if policy permits.

### Medium Risk

Medium-risk actions consume meaningful resources or influence future recommendations but do not directly change assets.

Examples:

```text
run remote training job
run expensive clustering job
generate embeddings for a large dataset
run multiple baseline probes
send summary-only packet to approved scientist provider
```

Medium-risk actions may run automatically if within budget and privacy constraints.

### High Risk

High-risk actions change important project assets or expose sensitive information.

Examples:

```text
create dataset improvement proposal
create new dataset version
modify labels
change benchmark role
send thumbnails to external provider
change remote host profile
create knowledge proposal
```

High-risk actions generally require approval or proposal conversion.

### Critical Risk

Critical-risk actions can affect production, organizational policy, or institutional truth.

Examples:

```text
deploy model
promote hypothesis to fact
change approved policy
overwrite benchmark
send raw data externally
launch expensive foundation-model training
delete dataset version
```

Critical-risk actions require explicit human approval.

---

## Approval Matrix

A simple starting approval matrix:

```text
Action                                  Default Decision
run small local experiment              allow
run SSH experiment within budget         allow or allow_with_warning
send summary to approved provider        allow
send plots to provider                   escalate_for_approval
send thumbnails to provider              escalate_for_approval
send raw samples to provider             block or escalate_for_approval
create human review queue                allow
modify labels                            escalate_for_approval
create dataset version                   escalate_for_approval
change label policy                      escalate_for_approval
change benchmark definition              escalate_for_approval
create knowledge proposal                allow
approve knowledge proposal               escalate_for_approval
promote hypothesis to fact               escalate_for_approval
update toolbox                           escalate_for_approval
deploy model                             escalate_for_approval
launch foundation training               escalate_for_approval
```

This matrix should eventually be configurable.

---

## Policy Checks

The decision system applies policy checks before execution.

Policy checks may include:

```text
privacy_policy
evaluation_policy
budget_policy
approval_policy
remote_execution_policy
dataset_comparability_policy
benchmark_policy
knowledge_governance_policy
toolbox_policy
deployment_policy
```

A recommendation must pass applicable policies before it can run.

If policies conflict, the decision system should escalate rather than guess.

---

## Privacy Checks

Privacy checks determine what data may leave which boundary.

The decision system should check:

```text
active privacy mode
scientist provider capabilities
data sensitivity
remote host trust level
allowed input types
knowledge-document sensitivity
report visibility
artifact transfer rules
```

Example:

A scientist provider may request representative thumbnails. If the active privacy mode is `summary_only_to_scientist`, the decision system should block or escalate.

Remote execution also has privacy implications. Copying raw data to a remote host is a data transfer and should be recorded.

---

## Budget Checks

The decision system should check whether an action fits the available budget.

Budget may include:

```text
wall time
GPU hours
CPU hours
memory
storage
remote transfer size
dollar cost
number of experiments
human review time
provider token cost
```

Budget estimates may be rough in early LASI.

The decision system should still record expected cost and actual cost when available.

Actions exceeding budget should be blocked or escalated.

---

## Tool Availability Checks

A recommendation may require a tool.

The decision system should check:

```text
tool exists in registry
tool supports problem type
tool supports dataset modality
tool supports execution backend
tool version is approved
tool is not deprecated
required dependencies are available
required artifacts exist
```

If a tool is unavailable, the recommendation should be blocked, deferred, or converted into a toolbox-change proposal.

---

## Duplicate Work Checks

LASI should avoid repeating experiments without reason.

The decision system should check whether the same or equivalent experiment has already been run on the same dataset version under comparable conditions.

Repeating an experiment may still be allowed if:

```text
prior run failed
prior run was partial_success
randomness needs confirmation
dataset changed
tool version changed
evaluation policy changed
scientist provider requested replication
human approved rerun
```

Duplicate runs should be intentional.

---

## Dataset Comparability Checks

The decision system should verify whether comparisons are valid.

It should check whether dataset versions, splits, label policies, benchmark roles, and evaluation policies are comparable.

If the scientist provider recommends comparing metrics across non-comparable dataset versions, the decision system should block the comparison or mark it as not comparable.

This protects LASI from claiming false improvement.

---

## Knowledge Governance Checks

The decision system governs knowledge-layer changes.

A scientist provider or knowledge curator may suggest a knowledge update, but the decision system determines whether it can be created, proposed, approved, or applied.

Suggested behavior:

```text
draft lesson proposal       → allow
draft contradiction warning → allow
approve lesson              → approval required
create fact                 → approval required
promote hypothesis to fact  → approval required
change policy               → approval required
retire policy               → approval required
```

The system should not automatically turn generated content into approved institutional knowledge.

---

## Deployment Checks

Deployment is a high-consequence action.

A model should not be deployed just because it performs well in validation.

Deployment checks may include:

```text
approved dataset version
approved benchmark result
evaluation policy satisfied
failure modes reviewed
human review completed if required
privacy policy satisfied
monitoring plan exists
rollback plan exists
owner assigned
project outcome status ready
```

Deployment logic may be mostly out of scope for the MVP, but the decision system should reserve authority over deployment recommendations.

---

## Stop and Escalation Logic

The decision system should support stopping and escalation.

Valid stop reasons include:

```text
low_expected_value
requires_human_review
requires_dataset_update
requires_label_policy_decision
budget_exhausted
blocked_by_privacy
blocked_by_missing_tool
blocked_by_remote_execution
insufficient_data
non_comparable_dataset_change
repeated_tool_failure
project_cancelled
```

Escalation means the system cannot or should not decide automatically.

Escalation should clearly state:

```text
what decision is needed
why automation is insufficient
who should decide
what evidence is available
what happens if no decision is made
```

---

## Decision Records

Every decision should be recorded.

A decision record should include:

```text
decision_id
project_id
recommendation_id
experiment_plan_id
decision_type
risk_level
allowed
blocked_reason
approval_required
approved_by
policy_results
budget_result
privacy_result
tool_result
comparability_result
created_at
notes
```

Decision records are part of operational memory.

They should be referenced in static reports when relevant.

---

## Decision Explanation

The decision system should produce explanations.

A good explanation is specific.

Bad:

```text
Blocked by policy.
```

Better:

```text
Blocked because the recommendation requires sending representative sample thumbnails to an external scientist provider, but the active privacy mode is summary_only_to_scientist.
```

Decision explanations should be useful to humans.

---

## Decision System Data Flow

A normal decision flow is:

```text
Recommendation is received
↓
Recommendation is normalized
↓
Experiment plan is compiled
↓
Risk level is assigned
↓
Policy checks are applied
↓
Budget checks are applied
↓
Privacy checks are applied
↓
Tool availability is checked
↓
Duplicate work is checked
↓
Comparability is checked
↓
Decision is recorded
↓
Action is allowed, blocked, escalated, converted, or stopped
```

The decision should occur before execution.

---

## Relationship to Scientist Provider

The scientist provider recommends a next action.

The decision system evaluates whether the recommendation is allowed.

If the recommendation is blocked, the decision system may ask for a revised recommendation, request human approval, or stop the project.

The scientist provider should not bypass the decision system.

---

## Relationship to Experiment Planner

The experiment planner converts a recommendation into an executable plan.

The decision system evaluates the plan.

Some checks require a compiled plan. For example, budget and tool availability checks may not be possible from the recommendation alone.

The planner and decision system should therefore work together:

```text
recommendation → draft plan → decision check → approved plan
```

---

## Relationship to Knowledge System

The decision system protects the knowledge layer.

Knowledge updates should flow through proposals and approvals.

A low-risk draft may be created automatically, but approving knowledge requires authority.

The decision system should prevent generated hypotheses from becoming approved facts without review.

---

## Relationship to Dataset System

The decision system protects dataset assets.

Dataset changes should be proposal-driven unless explicitly approved.

The decision system should require approval for:

```text
label modifications
new dataset versions
benchmark changes
class merges
class splits
label-policy changes
sample deletion
production dataset promotion
```

---

## Relationship to Reporting System

Reports should include important decisions.

The static report should show:

```text
scientist recommendation
decision outcome
reason for decision
blocked or escalated actions
approval requirements
stop reason
next required human decision
```

This makes the system auditable.

---

## MVP Decision Scope

The MVP decision system should support:

```text
allow
block
escalate_for_approval
stop_project
convert_to_proposal
```

It should check:

```text
privacy mode
budget estimate
tool availability
remote execution availability
dataset version status
duplicate experiment risk
approval requirement
```

The MVP does not need a sophisticated policy engine, complex role-based access control, deployment approval workflows, or learned expected-value estimation.

A simple deterministic decision gate is enough at first.

---

## Later Decision Abilities

Later versions may add:

```text
configurable approval matrix
role-based authority
learned cost estimates
provider recommendation scoring
tool usefulness-informed decisions
deployment readiness gates
knowledge governance automation
benchmark governance gates
multi-objective expected value
risk scoring
audit dashboards
```

These should be added only after the basic decision records and approval behavior are stable.

---

## Unsettled Questions

The first unsettled question is how much autonomy LASI should have in early use. The likely answer is that low-risk actions may run automatically, while dataset, knowledge, benchmark, deployment, privacy, and foundation-training actions require approval.

The second unsettled question is who counts as an approver. Solo use may use the operator. Team use may require project owner, data owner, domain expert, or engineering manager roles.

The third unsettled question is how to estimate expected value. The MVP can use simple categories such as low, medium, and high.

The fourth unsettled question is how to represent cost. GPU hours, wall time, token cost, remote transfer size, and human review time may all matter.

The fifth unsettled question is whether repeated low-risk actions should eventually require approval if they consume too much budget.

The sixth unsettled question is how strict duplicate-work detection should be. The system should prevent waste without blocking useful replication.

The seventh unsettled question is how to handle conflicting policies. The safest behavior is escalation.

---

## Out of Scope for This File

This file does not define the full database schema, user authentication, role-based access implementation, report template layout, deployment infrastructure, or detailed policy language.

Those belong in separate LASI documents.

This file defines how LASI authorizes, blocks, escalates, or stops actions.
