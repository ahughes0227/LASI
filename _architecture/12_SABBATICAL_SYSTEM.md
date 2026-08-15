# 12_SABBATICAL_SYSTEM.md

## Purpose

This document defines how LASI periodically reviews its own accumulated evidence, tools, assumptions, policies, lessons, and research direction.

The sabbatical system is responsible for structured reflection. It reviews project outcomes, experiment memory, tool usefulness, deployment failures, successful deployments, cancelled projects, active hypotheses, knowledge documents, external literature, and possible toolbox improvements.

It does not automatically change the toolbox, rewrite policies, promote hypotheses, or launch foundation-model training. It produces proposals for review.

The sabbatical system answers:

> Given what LASI has learned recently, what should the organization believe, test, update, retire, or investigate next?

---

## Core Idea

LASI should not only learn inside individual projects.

It should periodically step back and ask whether the overall research system is improving.

A normal project asks:

> What is limiting this model or dataset?

A sabbatical review asks:

> What is limiting the way we do research?

This distinction matters. A project may reveal that a dataset is label-limited. Many projects may reveal that the organization needs a stronger label-policy review process before model experimentation begins.

---

## Design Principles

### Review Before Change

The sabbatical system may recommend changes, but it should not apply them automatically.

It may propose new tools, retire weak tools, update policies, promote hypotheses, retire hypotheses, create literature summaries, or recommend foundation-model prototypes.

Humans approve high-consequence changes.

---

### Internal Evidence First

Sabbatical review should begin with LASI’s own evidence.

Internal evidence includes project outcomes, failed experiments, successful deployments, failed deployments, cancelled projects, tool usefulness records, human-review findings, dataset improvement results, and unresolved diagnostic patterns.

External literature is useful, but it should be interpreted in the context of actual LASI failures and opportunities.

---

### Ask What Should Change

A sabbatical review should not merely summarize what happened.

It should identify what the organization should believe differently, do differently, stop doing, or test next.

Useful outputs include proposals, not just commentary.

---

### Separate Evidence, Interpretation, and Proposal

A sabbatical review should distinguish:

```text
observed internal evidence
external literature evidence
interpretation
hypothesis
recommended proposal
required approval
```

This prevents the review from sounding more certain than the evidence supports.

---

## Sabbatical Review Scope

A sabbatical review may examine:

```text
project outcomes
deployment successes
deployment failures
validated-not-deployed projects
cancelled projects
blocked projects
experiment failures
low-value tool usage
high-value tool usage
scientist-provider recommendation outcomes
dataset improvement outcomes
human-review findings
knowledge-layer contradictions
stale hypotheses
external literature
new tool candidates
foundation-model opportunities
```

The scope should be configurable.

A lightweight monthly review may only examine recent projects and tool outcomes.

A deeper quarterly review may include literature, foundation opportunities, and policy review.

---

## Review Cadence

Suggested cadences:

```text
monthly_light_review
quarterly_deep_review
after_n_projects
after_n_dataset_versions
after_production_failure
after_major_toolbox_change
manual
```

A monthly review may ask whether recent projects revealed any recurring issue.

A quarterly review may ask whether the toolbox, policies, knowledge layer, or research direction should change.

An event-triggered review may occur after a production failure, repeated cancelled projects, or repeated low-value recommendations.

---

## Inputs

A sabbatical review should consume structured operational records and semantic knowledge.

### Operational Inputs

Operational inputs may include:

```text
project records
project outcome events
experiment plans
tool runs
remote runs
dataset versions
dataset characterizations
dataset comparisons
scientist reviews
decision records
human feedback
recommendation outcomes
tool usefulness records
artifact references
```

### Semantic Inputs

Semantic inputs may include:

```text
approved facts
approved policies
active hypotheses
tentative lessons
approved lessons
contradicted lessons
retired lessons
literature summaries
toolbox notes
diagnostic taxonomies
deployment retrospectives
```

### External Inputs

External inputs may include:

```text
recent papers
framework release notes
model architecture updates
benchmark changes
open-source tools
industry reports
internal research documents
vendor documentation
```

External inputs should be cited or referenced in the sabbatical artifact when used.

---

## Review Questions

A sabbatical review should ask practical questions.

Examples:

```text
Which tools repeatedly produced useful evidence?
Which tools repeatedly wasted compute?
Which scientist recommendations were confirmed by outcomes?
Which recommendations were contradicted?
Which project failures were preventable?
Which projects failed because of labels rather than models?
Which projects validated but did not deploy?
Which deployment failures reveal benchmark gaps?
Which lessons are stale?
Which hypotheses have enough evidence to promote?
Which policies caused repeated friction?
Which datasets suggest foundation-model opportunity?
Which new literature directly addresses recurring LASI failures?
```

The review should be oriented toward improving future decisions.

---

## Sabbatical Review Types

### Light Review

A light review summarizes recent outcomes and obvious action items.

It may run monthly or after a small number of projects.

It should be fast and low-overhead.

Outputs may include small knowledge proposals, warning notes, or follow-up tasks.

### Deep Review

A deep review examines broader patterns.

It may include tool usefulness analysis, scientist-provider calibration, dataset portfolio analysis, external literature review, and foundation-model opportunity review.

It may run quarterly or manually.

### Incident Review

An incident review occurs after a production failure, severe project failure, benchmark issue, privacy incident, or misleading recommendation.

It should focus on cause, prevention, and knowledge updates.

### Toolbox Review

A toolbox review focuses on tools.

It asks which tools should be added, changed, deprecated, or removed.

### Knowledge Review

A knowledge review focuses on facts, policies, hypotheses, lessons, literature, and taxonomies.

It asks whether the organization’s beliefs remain valid.

### Foundation Opportunity Review

A foundation opportunity review asks whether accumulated datasets and repeated failure patterns justify training or prototyping a reusable representation model.

---

## Outputs

A sabbatical review should produce structured outputs.

Possible outputs include:

```text
sabbatical_report
toolbox_change_proposal
knowledge_proposal
policy_update_proposal
hypothesis_promotion_proposal
hypothesis_retirement_proposal
dataset_portfolio_recommendation
foundation_opportunity_proposal
scientist_provider_adjustment_proposal
evaluation_policy_update_proposal
benchmark_review_proposal
```

The output should include evidence, interpretation, recommendation, risk, expected value, and approval requirements.

---

## Sabbatical Report

A sabbatical report is a static review artifact.

It should summarize:

```text
review scope
review period
projects reviewed
outcomes reviewed
major patterns
tool findings
knowledge findings
scientist-provider findings
dataset findings
external literature findings
recommended proposals
risks
unresolved questions
```

It should separate internal evidence from external research.

It should be saved as an artifact and referenced from the database.

---

## Proposal Types

### Toolbox Change Proposal

Recommends adding, updating, deprecating, or removing a tool.

Example:

```text
Add a label-noise diagnostic tool because three recent projects showed mixed-label clusters and the current workflow lacks a systematic label-noise estimate.
```

### Knowledge Proposal

Recommends adding or changing knowledge-layer documents.

Example:

```text
Promote the short-arc ambiguity hypothesis to an approved lesson because it appeared in four projects and was confirmed by human review in two.
```

### Policy Proposal

Recommends changing behavior rules.

Example:

```text
Require label-policy review before architecture sweeps when initial characterization finds low-purity clusters above a threshold.
```

### Hypothesis Retirement Proposal

Recommends retiring an unsupported belief.

Example:

```text
Retire the hypothesis that larger point-cloud transformers improve sparse scratch detection because three comparable projects showed no validation gain and higher cost.
```

### Foundation Opportunity Proposal

Recommends prototyping a reusable foundation or self-supervised model.

Example:

```text
Prototype a point-cloud geometry encoder because 18 dataset versions share sparse arc primitives and many projects are label-scarce.
```

---

## Relationship to Knowledge System

The sabbatical system should heavily interact with the knowledge layer.

It may review:

```text
facts
policies
hypotheses
lessons
literature summaries
toolbox notes
taxonomies
templates
```

It may propose updates, but it should not directly approve high-consequence knowledge changes.

Sabbatical review is one of the main mechanisms for preventing stale knowledge.

---

## Relationship to Outcome System

Project outcomes are central to sabbatical review.

The system should treat production outcomes as stronger evidence than offline validation alone.

A successful production deployment may strengthen a lesson.

A production failure may trigger contradiction review.

A cancelled project may reveal process problems.

A blocked project may reveal infrastructure or governance gaps.

Validated-not-deployed projects may reveal deployment-readiness issues.

---

## Relationship to Tool Registry

Sabbatical review should examine tool performance.

It should ask:

```text
Which tools were used?
Which tools failed?
Which tools produced useful evidence?
Which tools consumed budget without improving understanding?
Which tools are missing?
Which tools are deprecated or obsolete?
Which tools need better documentation?
```

Toolbox change proposals should reference evidence from tool-usefulness memory.

---

## Relationship to Scientist Provider

The scientist provider may assist with sabbatical review, but should not be the authority.

It can synthesize evidence, compare hypotheses, review literature summaries, and recommend proposals.

It should not approve proposals or directly change policies, knowledge, tools, or dataset definitions.

The review should record which scientist provider and prompt template were used.

---

## Relationship to Dataset Portfolio

Sabbatical review should inspect dataset evolution.

It should ask:

```text
Which dataset changes improved outcomes?
Which dataset changes failed to help?
Which datasets are repeatedly ambiguous?
Which benchmarks are stale?
Which label policies need review?
Which dataset families are candidates for reusable representation learning?
```

This helps LASI move from project-level data management to portfolio-level learning.

---

## Relationship to Foundation Recommender

Foundation-model opportunity review may be part of sabbatical mode or a separate system.

Sabbatical review can identify candidate domains and recommend deeper foundation opportunity analysis.

The foundation recommender should use sabbatical evidence but should produce its own structured proposal when needed.

---

## External Literature Review

External literature should be used to address specific LASI needs.

A literature review should not become a generic summary of recent ML papers.

It should ask:

```text
Which recent work addresses our recurring failures?
Which methods are mature enough to prototype?
Which methods are too experimental?
Which tools should be added to the toolbox?
Which assumptions in our current workflow are outdated?
```

Literature summaries should be saved in the knowledge layer, not buried inside a sabbatical report.

---

## Evidence Standards

Sabbatical recommendations should state evidence level.

Suggested evidence levels:

```text
single_project_signal
multi_project_pattern
human_review_confirmed
production_confirmed
literature_supported
contradicted_by_internal_evidence
insufficient_evidence
```

A proposal based on a single project should be treated differently from one supported by repeated production outcomes.

---

## Review Data Flow

A normal sabbatical review flow is:

```text
Review is triggered
↓
Review scope is selected
↓
Operational memory is queried
↓
Knowledge documents are retrieved
↓
External literature may be reviewed
↓
Patterns and contradictions are identified
↓
Scientist provider may synthesize evidence
↓
Sabbatical report is generated
↓
Proposals are created
↓
Humans review high-consequence proposals
↓
Approved changes update toolbox, policies, or knowledge
```

The review should create durable artifacts.

---

## Trigger Conditions

Sabbatical review may be triggered by:

```text
calendar cadence
number of completed projects
number of dataset versions
number of failed experiments
production failure
repeated cancelled projects
repeated low-value recommendations
new large unlabeled dataset
major toolbox update
manual request
```

Trigger rules should be configurable.

---

## Core Sabbatical Scope

The core system does not require fully automated sabbatical reviews.

The core system should support:

```text
manual sabbatical report generation
review of project outcomes
review of tool failures
review of approved/tentative knowledge documents
simple proposal drafting
static sabbatical report artifact
```

Full external literature review, automatic contradiction detection, and foundation-model opportunity scoring can wait.

---

## Later Sabbatical Abilities

Later versions may add:

```text
scheduled sabbatical reviews
external literature retrieval
automatic stale-knowledge detection
tool usefulness trend analysis
provider calibration review
foundation opportunity scan
policy friction analysis
benchmark health review
knowledge contradiction detection
automatic proposal bundling
```

These should be added after project outcomes, memory, and knowledge governance are stable.

---

## Risks

The first risk is overreaction. A single project failure should not cause broad policy changes without evidence.

The second risk is underreaction. Repeated failures may be ignored if no review process exists.

The third risk is literature chasing. LASI should not adopt every new method just because it is recent.

The fourth risk is stale assumptions. Old lessons may persist after tools, datasets, or operating conditions change.

The fifth risk is authority leakage. A scientist provider may make a proposal sound more certain than the evidence supports.

The sixth risk is review bloat. Sabbatical review should produce actionable proposals, not long summaries nobody uses.

---

## Unsettled Questions

The first unsettled question is cadence. Monthly light review and quarterly deep review are plausible, but the right cadence depends on project volume.

The second unsettled question is literature sourcing. Sources may include papers, vendor docs, framework releases, internal reports, or curated feeds.

The third unsettled question is who approves sabbatical proposals.

The fourth unsettled question is how much external research should be included in early LASI.

The fifth unsettled question is how to measure whether sabbatical recommendations improved the harness.

The sixth unsettled question is whether foundation opportunity review should live inside sabbatical mode or remain a fully separate workflow.

The seventh unsettled question is how aggressive the system should be in retiring old knowledge.

---

## Out of Scope for This File

This file does not define the full literature search implementation, proposal approval workflow, toolbox registry schema, knowledge governance details, foundation-model scoring model, or report template layout.

Those belong in separate LASI documents.

This file defines how LASI periodically reviews and improves its own research process.
