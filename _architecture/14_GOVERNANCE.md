# 14_GOVERNANCE.md

Workflow packages are validated fail-closed for unknown skills, capabilities, prompts,
rubrics, profiles, graph errors, artifact mismatches, and unsafe dynamic extension
policies. High-consequence nodes must declare a decision gate; dynamic tasks cannot
authorize execution.


## Purpose

This document defines how LASI governs authority, approvals, policies, high-consequence actions, review boundaries, and auditability.

The governance system is responsible for ensuring that LASI can run experiments and make recommendations without silently changing datasets, labels, benchmarks, institutional knowledge, privacy boundaries, production systems, or research policy.

It does not define specific database schemas, UI workflows, role-based access implementation, model training code, or deployment infrastructure. Those belong in separate LASI documents.

The governance system answers:

> Who or what is allowed to make a decision, what requires approval, and how does LASI prevent uncontrolled changes?

## User Operating Authority

The supported research surface is limited to `/lasi-start`, `/lasi-status`, `/lasi-pause`, `/lasi-resume`, `/lasi-cancel`, `/lasi-feedback`, and `/lasi-report`. `/lasi-build-capability` is the separate governed capability-development surface. It may create and validate draft packages and registration proposals, but does not authorize shared registration. Direct specialist commands are unsupported because they bypass durable scheduling. Pause and cancel are administrative controls, not permission to erase evidence. `/lasi-feedback` accepts only feedback matching the pending escalation identifier; LASI never supplies human discretion on the user's behalf.

---

## Core Idea

LASI is designed to help research move faster, but not by removing authority boundaries.

The scientist provider may recommend.

The local agent may orchestrate.

The experiment planner may compile plans.

The decision system may allow low-risk actions.

The tool registry constrains what can run.

The database records what happened.

The knowledge layer stores approved institutional learning.

Humans approve high-consequence changes.

Governance exists to preserve that separation.

---

## Design Principles

### Govern Boundaries, Not Every Iteration

Governance should minimize approval frequency without weakening authority
boundaries. Acceptance of an assignment authorizes routine reversible research
within its explicit scope. LASI may repeatedly explore, research, theorize, plan,
run allowed experiments, and review evidence without asking the operator to
approve each iteration. Deterministic decision records remain mandatory for
traceability, but they are produced by the decision system rather than treated
as human signoffs.

An approved remote host may be reused without repeated approval while trust,
privacy, data-transfer, budget, and tool conditions remain unchanged. Changing a
host trust profile or transferring data beyond the approved boundary still
requires human approval. Similarly, experimental composition of approved tools
is distinct from promotion into the shared toolbox; only promotion is governed
as a toolbox change.

Project-scoped experimental component approval is a delegated low-risk decision,
not toolbox governance. The component reviewer may approve it automatically only
after inspecting immutable source and evidence and establishing workdir-confined,
isolated execution with bounded dependencies and resources. The authorization is
valid for one project and component hash. Shared registration, changed source,
network/subprocess/secret access, native code, shared-state mutation, weakened
isolation, or material stability risk requires a new review and may require human
approval. This delegated authority cannot approve its own implementation request
or promote a component to the shared toolbox.

Plateau stopping is a scientific claim and therefore requires evidence: three or
four completed, valid, increasingly divergent attempts with no meaningful
improvement. Near-duplicate tuning and failed execution do not satisfy that
threshold. A true blocker is a condition that cannot be resolved inside the
assignment without human discretion or new authority, not ordinary uncertainty.

### Authority Must Be Explicit

No subsystem should silently assume authority it does not have.

A model provider should not approve its own recommendation.

An experiment worker should not create a new dataset version without the dataset system.

A knowledge curator should not promote a hypothesis to a fact without approval.

A report should not make an unapproved lesson look like institutional policy.

Authority should be visible in records, reports, and proposals.

---

### High-Consequence Actions Require Review

Some actions can permanently change the research record, dataset meaning, institutional memory, privacy posture, benchmark validity, or production behavior.

These actions require explicit approval.

Governance should focus on those actions first.

Low-risk diagnostic work can be automated more freely.

---

### Proposals Before Changes

Many high-consequence actions should first become proposals.

A proposal gives reviewers a structured object to evaluate before anything changes.

Examples include:

```text
dataset improvement proposal
knowledge proposal
toolbox change proposal
policy update proposal
benchmark change proposal
deployment proposal
foundation model prototype proposal
```

Proposals preserve the reason for a change.

---

### Auditability Matters

Every approval, rejection, override, policy exception, and high-consequence decision should be recorded.

A future reviewer should be able to answer:

```text
Who approved this?
What evidence was available?
What policy applied?
What changed?
What alternatives were rejected?
What risk was accepted?
```

Governance records are part of operational memory.

---

## Authority Boundaries

LASI should enforce the following authority boundaries.

The scientist provider recommends but does not execute.

The experiment planner translates recommendations into possible plans but does not authorize high-risk actions.

The decision system authorizes, blocks, escalates, or converts recommendations into proposals.

The tool registry defines what tools may run.

The dataset system owns dataset versions, lineage, comparability, and benchmark roles.

The knowledge system owns semantic memory.

The knowledge curator drafts changes but does not approve them.

The outcome system records project outcomes.

Humans approve high-consequence changes.

---

## Governance Domains

LASI governance covers several domains.

### Experiment Governance

Experiment governance decides which experiments can run automatically and which require approval.

Low-risk experiments may run automatically if they are within budget and policy.

Expensive, remote, privacy-sensitive, or repeated experiments may require approval.

### Dataset Governance

Dataset governance protects dataset meaning.

It governs label changes, class merges, class splits, benchmark updates, dataset version creation, sample deletion, synthetic data inclusion, and production dataset promotion.

### Knowledge Governance

Knowledge governance protects institutional memory.

It governs facts, policies, hypotheses, lessons, literature summaries, toolbox notes, taxonomies, and templates.

### Privacy Governance

Privacy governance controls what data may leave which boundary.

It governs scientist-provider inputs, remote execution, report sharing, artifact exports, and knowledge document exposure.

### Benchmark Governance

Benchmark governance protects evaluation integrity.

It governs benchmark creation, refresh, retirement, label audit, and comparability.

### Toolbox Governance

Toolbox governance controls tool additions, deprecations, changes, and approved usage.

Capability development is governed as toolbox expansion. Deduplication,
research, scaffolding, implementation, and validation may occur before approval.
Shared registration requires a package-hash-bound proposal and an explicit
`update_toolbox` approval. The builder, validator, or registrar cannot approve
its own proposal, and changed package content invalidates prior validation.

Component development is governed by the same toolbox boundary. Component
packages and `ComponentRegistry` remain authoritative; `PlannerCatalog` is a
rebuildable discovery projection and never grants execution authority.

### Provider Governance

Provider governance controls which scientist providers may be used and what each provider may receive.

### Deployment Governance

Deployment governance controls whether a model, method, report, or recommendation may enter production use.

### Outcome Governance

Outcome governance controls who can mark a project as deployed, successful in production, failed in production, cancelled, blocked, or archived.

---

## High-Consequence Actions

High-consequence actions require explicit review.

Examples include:

```text
modify labels
create new dataset version
delete dataset samples
merge classes
split classes
change label policy
change benchmark definition
promote dataset to benchmark
send raw data externally
send thumbnails externally
change approved privacy policy
change scientist provider profile
approve knowledge fact
approve policy change
promote hypothesis to fact
retire approved knowledge
update toolbox
deprecate tool
deploy model
mark model successful in production
launch foundation-model training
```

The system should default to escalation when uncertain.

---

## Low-Risk Actions

Low-risk actions may be automated if policy allows.

Examples include:

```text
validate manifest
run small local characterization
generate static report
query prior records
retrieve approved knowledge
run small baseline within budget
draft knowledge proposal
draft dataset improvement proposal
create human review queue
```

Low-risk does not mean unlogged.

All actions should still be recorded.

---

## Approval Records

Every approval should produce a record.

An approval record should include:

```text
approval_id
project_id
proposal_id
action_type
risk_level
requested_by
approved_by
approval_status
approval_reason
conditions
created_at
expires_at
related_policy
related_artifacts
```

Approval records should be linked to the action they authorize.

If approval is conditional, the conditions should be machine-readable where possible.

---

## Proposal Records

A proposal is a structured request for a change.

A proposal should include:

```text
proposal_id
proposal_type
project_id
source
recommendation_id
summary
evidence
expected_value
risk
affected_assets
approval_required
status
created_at
```

Proposal statuses may include:

```text
draft
submitted
under_review
approved
rejected
deferred
superseded
withdrawn
implemented
```

A proposal should not be treated as implemented until the corresponding action is executed and recorded.

---

## Policy Records

Policies should be explicit.

A policy may live as a markdown document in the knowledge layer and may also have a structured representation in the database for enforcement.

Examples of policy categories:

```text
privacy_policy
budget_policy
dataset_policy
benchmark_policy
knowledge_policy
toolbox_policy
provider_policy
deployment_policy
remote_execution_policy
report_sharing_policy
```

A policy should include owner, version, effective date, status, and scope.

---

## Policy Precedence

Policies may conflict.

When policies conflict, LASI should not guess.

The safe default is escalation.

Example:

A project policy may allow thumbnails to be sent to a scientist provider, but the organization privacy policy may forbid it.

In that case, the stricter policy should apply or the action should escalate for review.

Policy precedence should eventually be formalized.

---

## Roles

LASI names conceptual authority roles without requiring a full role-based access system for personal-computer operation.

Possible roles include:

```text
operator
project_owner
data_owner
domain_expert
reviewer
approver
knowledge_owner
toolbox_owner
benchmark_owner
deployment_owner
administrator
```

In solo use, one person may occupy all roles.

In team use, roles become important.

Role implementation can wait, but the documents should avoid assuming that the scientist provider or local agent has approval authority.

---

## Dataset Governance

Dataset governance controls changes to dataset assets.

Actions requiring approval should include:

```text
label modification
class merge
class split
label-policy change
new benchmark creation
benchmark refresh
sample deletion
synthetic data admission
production dataset promotion
dataset version promotion
```

Dataset governance should preserve lineage and comparability.

If a dataset change alters task meaning, LASI should record that metrics are not directly comparable to prior versions.

---

## Benchmark Governance

Benchmarks require stronger protection than ordinary datasets.

Benchmark governance should answer:

```text
Who can create a benchmark?
Who can modify a benchmark?
When is a benchmark retired?
How are benchmark labels audited?
What happens when label policy changes?
How is benchmark overfitting prevented?
```

A frozen benchmark should not be overwritten.

If the label policy changes, create a new benchmark version and preserve the old one.

---

## Knowledge Governance

Knowledge governance protects semantic memory.

The most important rule is that facts, policies, hypotheses, and lessons are not interchangeable.

A hypothesis may be useful but unproven.

A lesson may be project-specific.

A policy may be authoritative even when evidence is incomplete.

A fact should require stronger evidence and review.

Knowledge governance should control:

```text
fact creation
policy change
hypothesis promotion
hypothesis retirement
lesson approval
lesson retirement
contradiction resolution
taxonomy update
template update
literature summary approval
```

The knowledge curator may draft changes.

Humans approve high-consequence knowledge updates.

---

## Privacy Governance

Privacy governance controls data movement and exposure.

It applies to:

```text
scientist provider inputs
remote execution staging
artifact exports
report sharing
knowledge retrieval
sample visualization
thumbnail generation
raw data movement
```

Privacy modes may include:

```text
local_only
summary_only_to_scientist
plots_allowed
thumbnails_allowed
raw_samples_allowed
knowledge_allowed
```

The decision system should enforce privacy mode before data leaves a boundary.

---

## Remote Execution Governance

Remote execution is a data-transfer and compute boundary.

Remote execution governance should control:

```text
approved host profiles
host trust levels
allowed datasets per host
allowed artifact transfer
remote cleanup policy
remote credential handling
remote environment requirements
```

Changing a remote host profile should require approval if it affects trust, data movement, or credentials.

---

## Scientist Provider Governance

Scientist provider governance controls which providers may be used.

It should define:

```text
approved providers
allowed input types
privacy capabilities
token or cost limits
authoritative token-usage receipt retention
no-estimation policy for token counts or billed cost
timeout policy
fallback policy
raw response retention
provider profile ownership
```

The scientist provider should be configurable, but not uncontrolled.

Adding or changing a provider profile can change privacy, cost, and recommendation behavior.

---

## Toolbox Governance

Toolbox governance controls tools.

It should answer:

```text
Who can add a tool?
Who can deprecate a tool?
How is a tool tested?
What schema is required?
What failure modes are documented?
What problem types is the tool approved for?
What toolbox version introduced the tool?
```

Sabbatical review may recommend toolbox changes, but approval is required.

---

## Deployment Governance

Deployment execution is outside the current research harness, but LASI reserves its authority boundaries.

Deployment should require evidence beyond offline metrics.

Deployment approval may require:

```text
approved dataset version
approved benchmark result
failure-mode review
owner assignment
monitoring plan
rollback plan
privacy review
human review completion
operational acceptance
```

A model should not be deployed just because a scientist provider recommends it.

---

## Outcome Governance

Outcome status affects memory.

Therefore, outcome governance matters.

Marking a model `successful_in_production` should require evidence.

Marking a model `failed_in_production` should preserve evidence and trigger review.

Changing a project from `cancelled` to `deployed` should be recorded as an event, not an overwrite.

Outcome changes should be append-only when possible.

---

## Override Handling

Humans may override LASI recommendations or decision blocks.

Overrides should be recorded.

An override record should include:

```text
override_id
project_id
decision_id
overridden_by
original_decision
new_decision
reason
risk_acknowledged
created_at
```

Overrides are not inherently bad.

They are important evidence.

If overrides repeatedly succeed, policy may be too strict.

If overrides repeatedly fail, policy may be too weak or reviewers may need better evidence.

---

## Exceptions

Some policy exceptions may be allowed.

Exceptions should be explicit, scoped, and time-limited where possible.

An exception should record:

```text
exception_id
policy
scope
reason
approved_by
start_date
end_date
conditions
```

Silent exceptions are dangerous because they destroy auditability.

---

## Audit Trail

LASI should preserve an audit trail for high-consequence actions.

The audit trail should include:

```text
recommendations
experiment plans
decision records
approval records
policy checks
dataset changes
knowledge changes
benchmark changes
provider calls
remote execution records
deployment outcomes
overrides
exceptions
```

The audit trail should allow reconstruction of why the system behaved as it did.

---

## Governance and Reports

Reports should display important governance information.

A report should show:

```text
decision status
approval requirements
blocked actions
escalated actions
active privacy mode
provider profile
dataset comparability
benchmark status
outcome status
knowledge documents used
policy warnings
```

A report should not hide that an action was blocked or required approval.

---

## Governance and Sabbatical Review

Sabbatical review should evaluate governance friction.

It should ask:

```text
Which policies blocked useful work?
Which missing policies caused problems?
Which approvals were repeatedly needed?
Which overrides succeeded?
Which overrides failed?
Which governance rules are stale?
```

Governance should evolve based on evidence.

---

## Core Governance Scope

Governance should remain proportional to the operating environment and consequence level.

The governance system should support:

```text
risk classification
approval_required flag
decision records
blocked reasons
basic privacy enforcement
basic budget enforcement
basic dataset-change approval requirement
basic knowledge-change proposal requirement
basic remote-host approval flag
outcome event history
```

Full role-based access control, pull-request automation, enterprise approval routing, deployment signoff workflow, and complex policy engines should be introduced only when the operating environment requires them.

Simple explicit gates are enough at first.

---

## Later Governance Abilities

Later versions may add:

```text
role-based authority
approval workflows
policy engine
policy precedence rules
audit dashboard
override analytics
exception expiration
report signoff
deployment readiness gates
benchmark approval workflows
knowledge pull-request automation
provider governance dashboard
```

These should be added after the core decision and approval records are stable.

---

## Risks

The first risk is over-governance. Too much approval friction can make LASI unusable.

The second risk is under-governance. Too little control can allow silent dataset, benchmark, privacy, or knowledge corruption.

The third risk is authority leakage. Agents or model providers may appear to make decisions they are only supposed to recommend.

The fourth risk is invisible exceptions. Unrecorded policy exceptions destroy trust.

The fifth risk is stale governance. Rules that made sense early may become obstacles later.

The sixth risk is solo-to-team transition. A system that works for one operator may need stronger governance when multiple people use it.

---

## Unsettled Questions

The first unsettled question is who counts as an approver in each deployment. Solo use may treat the operator as approver.

The second unsettled question is whether approvals should be stored only in the database or also represented in markdown governance records.

The third unsettled question is how strict benchmark governance needs to be before production use.

The fourth unsettled question is how to implement role-based authority later without redesigning the system.

The fifth unsettled question is how to handle policy conflicts. The safe starting point is escalation.

The sixth unsettled question is how often governance policies should be reviewed.

The seventh unsettled question is which actions should be allowed automatically as the system matures.

---

## Out of Scope for This File

This file does not define user authentication, enterprise authorization integration, full policy-engine implementation, database schemas, deployment infrastructure, or approval UI.

Those belong in separate LASI documents.

This file defines how LASI thinks about authority, approval, and controlled change.
