# 07_SCIENTIST_PROVIDER.md

## Purpose

This document defines the role, boundaries, inputs, outputs, and provider abstraction for the LASI scientist provider.

The scientist provider is the reasoning layer that reviews evidence and recommends next actions. It may be backed by a frontier model, local model, mocked provider, or future model endpoint.

It does not execute tools, modify datasets, approve decisions, update knowledge, or become the source of truth.

The scientist provider answers:

> Given the available evidence, what is likely limiting performance, what should be tested next, and is further work justified?

---

## Core Idea

The scientist provider acts like a senior scientist.

It reviews structured evidence, compares hypotheses, identifies likely performance limiters, recommends next actions, and explains uncertainty.

It should not behave like an autonomous agent with unrestricted tool access.

LASI must remain model-provider agnostic. The system should not be tied to Vertex, OpenAI, Anthropic, a local LLM, or any single vendor.

The provider is interchangeable because LASI owns the contracts.

---

## Design Principles

### Provider Agnostic

LASI should support multiple scientist providers through a stable interface.

Possible provider types include:

```text
mock_provider
local_model
vertex
openai
anthropic
internal_api
future_provider
```

The rest of LASI should not care which provider produced the review as long as the response conforms to the `ScientistReview` contract.

Provider-specific behavior should be isolated behind adapter code.

---

### Evidence First

The scientist provider must reason from the diagnostic packet and retrieved knowledge context.

It should not invent facts, assume unavailable data, or recommend actions unsupported by evidence.

If evidence is insufficient, it should say so.

A weak but honest review is better than a confident unsupported one.

---

### Recommend, Do Not Execute

The scientist provider recommends.

It does not execute.

It does not call tools.

It does not modify data.

It does not update the database.

It does not write to the knowledge layer.

It does not approve high-consequence actions.

The local decision system and experiment planner mediate all execution.

---

### Structured Output

The scientist provider must return structured output.

Freeform prose may be included as explanation, but the actionable content must be machine-readable.

The local decision system should reject malformed, unsupported, or out-of-policy recommendations.

---

### Traceability

Every scientist review should record:

```text
provider_profile
model_name
prompt_template_version
diagnostic_packet_id
knowledge_documents_used
response_schema_version
created_at
raw_response_artifact
normalized_review
provider/runtime token usage receipt when available
explicit unavailable metering state when it is not
```

This allows future reviewers to understand what model produced a recommendation and what context it used.

---

## Provider Profiles

A provider profile defines how LASI connects to a scientist provider.

A profile should include:

```text
provider_id
provider_type
model_name
endpoint
authentication_reference
temperature
determinism_settings
timeout_seconds
retry_policy
token_budget
privacy_capabilities
allowed_input_types
response_format
enabled
```

Provider credentials should not be stored directly in project configs.

Project configs should reference provider profiles by ID.

This prevents portable project files from leaking API keys or internal endpoint details.

---

## Supported Provider Modes

### Mock Provider

The mock provider returns deterministic test responses.

It is required for testing.

The mock provider should be available before any real model provider.

It allows LASI to test workflows, reports, decision gates, and failure handling without depending on external model availability.

### Local Provider

The local provider runs on local or internal infrastructure.

It may be useful when privacy rules prevent external model calls.

A local provider may be weaker than a frontier model, but it can still provide useful structured review if the prompt and packet are well designed.

### External Frontier Provider

An external frontier provider may offer stronger reasoning.

It may also introduce privacy, cost, latency, and availability constraints.

The decision system and privacy policy determine whether external providers may receive summaries, plots, thumbnails, raw samples, or knowledge documents.

### Future Provider

The provider interface should allow new models to be added without rewriting the harness.

New providers should implement the same input/output contracts and pass the same provider conformance tests.

---

## Scientist Review Inputs

The scientist provider receives a diagnostic packet.

The diagnostic packet should be structured and bounded.

It may include:

```text
project summary
problem type
dataset version
dataset characterization summary
evaluation policy
model comparison table
learning curve summary
error analysis summary
cluster analysis summary
calibration summary
dataset comparability notes
experiment history
current project state
budget remaining
allowed recommendation types
privacy mode
open questions
retrieved knowledge context
```

The provider should receive summaries, not uncontrolled raw logs.

Raw samples, thumbnails, or plots may be included only if the active privacy policy allows them.

---

## Knowledge Context

The scientist provider may receive relevant knowledge documents.

Knowledge context may include:

```text
approved facts
approved policies
active hypotheses
approved lessons
tentative lessons
literature summaries
toolbox guidance
diagnostic taxonomy entries
similar project outcomes
```

Knowledge retrieval should be bounded and recorded.

The scientist provider should know the type and status of each document.

For example, a policy should be treated as more authoritative than a tentative lesson. A contradicted lesson should be treated as cautionary context, not positive evidence.

---

## Scientist Review Output

The provider returns a `ScientistReview`.

A review should include:

```text
review_id
primary_diagnosis
diagnosis_confidence
supporting_evidence
counter_evidence
alternative_hypotheses
recommended_next_action
expected_value
estimated_cost
stop_recommendation
escalation_required
human_review_required
knowledge_references
evidence_references
uncertainty_notes
```

The review should distinguish:

```text
observed evidence
inference
hypothesis
recommendation
policy constraint
uncertainty
```

This distinction is critical. A hypothesis should not be phrased as an observed fact.

---

## Primary Diagnosis

The primary diagnosis identifies the most likely current limiter.

Examples:

```text
label_ambiguity
data_coverage
model_capacity
representation_gap
preprocessing_issue
domain_shift
threshold_policy
benchmark_leakage
insufficient_benchmark_quality
```

The diagnosis should use the controlled diagnostic taxonomy.

If no single diagnosis is well supported, the provider should say that the evidence is insufficient and recommend a clarifying experiment.

---

## Supporting Evidence

Supporting evidence should reference diagnostic-packet fields or retrieved knowledge documents.

Bad:

```text
The model is probably too small.
```

Better:

```text
Model capacity is plausible because both training and validation performance improved when capacity increased, and training loss remains high.
```

Best:

```text
Model capacity is plausible because run_014 improved validation F1 from 0.82 to 0.88 while reducing training loss, and the model-size scaling curve has not saturated. However, short-arc recall remains weak, so data coverage remains an alternative hypothesis.
```

Evidence should be specific enough for the report to trace.

---

## Counter-Evidence

A good scientist review should include counter-evidence.

For example, if the provider diagnoses model capacity, it should mention evidence that weakens the diagnosis.

Counter-evidence prevents one-sided recommendations.

Example:

```text
Model capacity is supported by scaling behavior, but the low-purity short-arc cluster suggests that label ambiguity may also be limiting performance.
```

---

## Alternative Hypotheses

The scientist provider should list plausible alternatives.

Each alternative should include:

```text
hypothesis
confidence
supporting_evidence
test_that_would_distinguish_it
```

Alternative hypotheses are important because many industrial ML failures are mixed-cause failures.

A model can be both data-limited and label-limited.

A dataset can be both undercovered and poorly defined.

---

## Recommended Next Action

The scientist provider should recommend one next action.

The action should use an allowed recommendation type.

Examples:

```text
run_experiment
run_error_analysis
run_learning_curve
run_embedding_analysis
create_human_review_queue
create_dataset_improvement_proposal
stop_low_expected_value
collect_more_data
revise_label_policy
compare_against_prior_dataset
update_report_only
```

The provider may also include secondary suggestions, but the primary recommendation should be clear.

The local decision system determines whether the recommendation is allowed.

---

## Expected Value

The review should estimate expected value.

Expected value does not mean guaranteed metric improvement.

It means the likely value of the next action given cost, uncertainty, and diagnostic usefulness.

Examples:

```text
High expected value:
Human review of mixed-label Cluster 12 is likely to clarify whether the project is label-policy limited.

Low expected value:
A larger model sweep is unlikely to help because three architectures already plateaued at similar validation performance.
```

Expected value should consider information gain, not only performance gain.

---

## Stop Recommendations

The scientist provider may recommend stopping.

Valid stop reasons include:

```text
low_expected_value
requires_human_review
requires_dataset_update
requires_label_policy_decision
budget_exhausted
insufficient_data
non_comparable_dataset_change
blocked_by_privacy
blocked_by_missing_tool
```

Stopping is not failure.

A good stop recommendation can prevent wasted work.

For example, stopping because label policy is unclear is a successful diagnostic outcome.

---

## Human Review Recommendations

The provider may recommend human review.

Human review is appropriate when:

```text
labels appear ambiguous
low-purity clusters contain mixed labels
high-confidence wrong predictions suggest label errors
class definitions appear unstable
domain policy is needed
false-positive and false-negative costs are unclear
deployment acceptability is uncertain
```

The recommendation should describe what should be reviewed and why.

It should not simply say “ask a human.”

---

## Dataset Change Recommendations

The provider may recommend dataset changes, but it should not directly create or modify dataset versions.

Dataset-related recommendations should become dataset improvement proposals.

Examples:

```text
add targeted examples from short-arc ambiguity region
audit labels in Cluster 12
split class into two subclasses
merge operationally equivalent classes
create frozen benchmark version
collect examples from underrepresented tool family
```

The dataset portfolio system and decision system handle approval and implementation.

---

## Knowledge Update Recommendations

The scientist provider may recommend knowledge updates.

It may suggest:

```text
new lesson
hypothesis promotion
hypothesis retirement
policy review
taxonomy update
toolbox note
sabbatical review item
```

However, it must not modify the knowledge layer directly.

Knowledge changes should become knowledge proposals.

Humans approve high-consequence knowledge updates.

---

## Invalid Recommendations

The local decision system should reject invalid recommendations.

Invalid recommendations include:

```text
action type not allowed
tool not in registry
missing evidence
malformed confidence
privacy violation
budget violation
requires unavailable data
requires unavailable remote host
direct dataset modification
direct knowledge-layer modification
direct deployment
unsupported claim
```

Invalid recommendations should be recorded.

They may indicate a prompt problem, provider limitation, or missing tool.

---

## Provider Normalization

Different model providers may return different native formats.

LASI should normalize all provider outputs into the same `ScientistReview` schema.

Provider adapters should handle:

```text
request formatting
response parsing
schema validation
retry behavior
error handling
raw response capture
normalized review generation
```

The rest of LASI should interact only with normalized reviews.

---

## Provider Error Handling

Provider calls may fail.

Failure modes include:

```text
timeout
rate_limit
authentication_failure
invalid_response
schema_validation_failure
content_filter_block
network_error
provider_unavailable
cost_limit_exceeded
privacy_policy_block
```

The harness should record the failure and decide whether to retry, fall back to another provider, use a mock provider, run without scientist review, or stop.

Provider failure should not corrupt project state.

---

## Provider Comparison

Later versions may compare scientist providers.

The system may ask:

```text
Which provider produced more useful recommendations?
Which provider was better calibrated?
Which provider made unsupported claims?
Which provider was cheaper for similar diagnostic value?
Which provider followed schema reliably?
```

Provider comparison should be based on recommendation outcomes, not subjective preference.

This is not required for the MVP.

---

## Confidence Calibration

The scientist provider may give confidence scores, but LASI should treat them cautiously.

Provider confidence is not ground truth.

Over time, LASI should compare provider confidence to later outcomes.

For example:

```text
Provider diagnosed label ambiguity at 0.82 confidence.
Human review later confirmed inconsistent labels.
```

or:

```text
Provider diagnosed model capacity at 0.76 confidence.
Scaling tests contradicted this; larger models overfit without validation gain.
```

This allows future calibration.

---

## Privacy and Provider Context

The provider must respect the active privacy mode.

Possible privacy modes include:

```text
local_only
summary_only_to_scientist
plots_allowed
thumbnails_allowed
raw_samples_allowed
knowledge_allowed
```

The diagnostic packet builder should remove or redact data that is not allowed under the active mode.

If privacy restrictions prevent useful review, the provider should state what evidence is missing.

---

## Mock Provider Requirement

The mock provider is required.

It should allow deterministic tests for:

```text
valid scientist review
invalid action type
malformed response
low-confidence diagnosis
stop recommendation
human-review recommendation
dataset-change recommendation
provider failure
```

The mock provider makes the harness testable without external API calls.

---

## Scientist Provider Data Flow

A normal provider flow is:

```text
Project state is loaded
↓
Diagnostic packet is assembled
↓
Relevant knowledge context is retrieved
↓
Privacy policy filters packet and context
↓
Provider profile is selected
↓
Request is sent
↓
Raw response is captured
↓
Response is normalized
↓
Schema is validated
↓
Scientist review is recorded
↓
Decision system evaluates recommendation
```

The provider never directly executes the recommendation.

---

## Scientist Provider and Reports

Static reports should include the scientist review.

The report should show:

```text
provider profile
model name
review timestamp
primary diagnosis
confidence
supporting evidence
counter-evidence
alternative hypotheses
recommended next action
expected value
stop recommendation
knowledge documents used
```

This makes the recommendation auditable.

---

## MVP Scientist Provider Scope

The MVP should support:

```text
mock provider
one configured real provider or local provider
structured diagnostic packet
structured ScientistReview response
schema validation
raw response artifact capture
provider profile recording
basic provider error handling
privacy-mode filtering
exact provider/runtime token telemetry with explicit unavailable coverage
```

The MVP does not need provider comparison, confidence calibration, multi-provider voting, automatic fallback chains, or advanced prompt optimization.

---

## Later Scientist Provider Abilities

Later versions may add:

```text
multi-provider comparison
provider confidence calibration
provider usefulness scoring
provider fallback chains
provider-specific prompt tuning
local-only scientist mode
review critique mode
sabbatical scientist mode
foundation-opportunity scientist mode
```

These should be added only after the base provider contract is stable.

---

## Unsettled Questions

The first unsettled question is which real provider should be supported first. The mock provider should come first regardless.

The second unsettled question is how much context should be sent to the provider. More context is not always better.

The third unsettled question is whether plots and thumbnails are allowed in the first real provider integration.

The fourth unsettled question is how strict evidence references should be in Phase 1. The long-term goal is strong traceability, but the MVP may use simpler references.

The fifth unsettled question is how to handle provider disagreement if multiple providers are used later.

The sixth unsettled question is how much prompt text belongs in this system versus the knowledge/template system.

The seventh unsettled question is how to measure whether a provider recommendation was useful.

---

## Out of Scope for This File

This file does not define the full diagnostic packet schema, exact prompt templates, provider SDK implementation, report HTML layout, decision-gate rules, or database schemas.

Those belong in separate LASI documents.

This file defines the role and boundaries of the scientist provider.
