# 04_EXPERIMENT_SYSTEM.md

## Purpose

This document defines how LASI plans, runs, records, compares, and interprets experiments.

The experiment system is responsible for turning dataset versions into evidence. It defines experiment plans, tool runs, execution backends, reproducibility expectations, result logging, failure handling, and how experiment results are prepared for scientist review.

It does not define dataset storage, scientist-provider prompts, database table schemas, report templates, or governance policy in detail. Those belong in separate LASI documents.

The experiment system answers:

> What did we run, why did we run it, what happened, and what does that result tell us?

## Durable Research Control Loop

Experiments sit inside a durable observe, hypothesize, criticize, plan,
decision-check, test, interpret, and criticize-results loop. The planning-only
coordinator returns a versioned `TaskGraphProposal`. The runtime records accepted
tasks and dependencies in SQLite, leases ready tasks to specialists, validates
their `AgentResult`, and appends every transition. The coordinator never executes
the tasks it proposes, and agents never update operational state directly.

Every material performance result or mechanism claim is a scientific checkpoint.
The runtime schedules an independent critic that tries to disprove it, checks
metric integrity and hidden regressions, and proposes discriminating
falsification tests. A material unresolved criticism becomes a bounded
falsification-planning task. Valid non-improving attempts must still become
increasingly divergent; near-duplicate tuning does not consume plateau patience.

---

## Core Idea

Experiments are isolated semantic subcontexts in addition to being structured
experiment records. A project may keep `20_work/experiments/<experiment_id>/`
with its hypothesis, inputs, configuration, results, artifacts, and critique.
These files are readable context for that experiment; metrics and run state still
belong in the database and MLflow.

In LASI, an experiment is not just a model training run.

An experiment is a controlled attempt to answer a specific research question.

Examples:

```text
Does a larger model improve validation performance?
Does more data improve short-arc recall?
Do engineered arc features help?
Are the remaining errors concentrated in one cluster?
Does higher input resolution reduce false negatives?
Does the historical best model for similar datasets work here?
```

Every experiment should have a reason, an expected signal, a defined dataset version, a known execution environment, a set of expected artifacts, and a result that can be interpreted later.

Every durable experiment action must also produce an append-only project token
telemetry record in operational memory. This includes deterministic actions,
which are explicitly recorded as `not_applicable`, and agent/provider actions,
which are `reported` only when an authoritative runtime receipt is available or
`not_available` when it is not. A readable project ICM telemetry file may
project this ledger, but it is never the source of truth.

---

## Design Principles

### Persistent Research Loop

A user assignment starts a persistent bounded loop:

```text
observe → hypothesize → criticize → plan → decision → test → interpret
   ↑                                                        │          │
   └──── next uncertainty ← falsify/replicate ← criticize ──┴──────────┘
```

The loop continues without conversational approval for low-risk plans that pass
the deterministic decision gate and remain inside the assignment's dataset,
privacy mode, budget, benchmark policy, registered tools or components, and
approved execution backends. Each experiment still has its own `ExperimentPlan`,
`DecisionRecord`, evidence, and closeout; internal authorization is not a human
approval request.

### Increasing Divergence

Every attempt records an approach signature, research basis, novelty score, and
novel dimensions. After a completed attempt fails to produce a meaningful
objective improvement, the novelty floor rises. Later attempts should move from
parameter tuning toward changes in model family, representation, feature
construction, objective, validation design, data view, or algorithmic
assumptions. LASI may compose more sophisticated approved components, but
experimental use does not silently promote new code into the toolbox.

If the coordinator needs a new component, it issues a `ComponentRequest` rather
than pausing the assignment. A separate component-review agent checks the source
hash, dependencies, strict configuration and artifact interfaces, tests,
resource bounds, isolation, filesystem confinement, and access to network,
subprocesses, providers, secrets, native code, or shared state. Safe requests are
approved automatically for project-scoped experimental execution. Missing tests
or other correctable stability evidence return to the builder without human
interruption. Only genuine security/system-stability risk or shared promotion
requires human discretion.

A near-duplicate candidate is rejected before execution when possible. It does
not count as evidence of a plateau. A recoverable failed run is retained as
evidence and routes back to exploration, but likewise does not count as a valid
non-improving attempt.

### Evidence-Based Plateau

The default plateau patience is four and may be configured to three. A plateau
exists only after that many completed, valid, sufficiently novel attempts in a
row fail to exceed the best comparable score by the evaluation policy's minimum
meaningful improvement. An improvement resets both patience and novelty pressure.
Iteration or compute limits remain separate budget stop conditions; LASI must not
claim it found a global optimum merely because it reached a plateau.

### Experiments Generate Evidence

The goal of an experiment is not always to improve a metric.

Some experiments are valuable because they reveal that additional model training is low value, that labels are ambiguous, that data coverage is insufficient, or that a dataset update did not address the expected gap.

The experiment system should treat information value as meaningful, even when performance does not improve.

---

### Plans Before Execution

LASI should not allow the scientist provider or local agent to call tools directly without an experiment plan.

A recommendation should be converted into an `ExperimentPlan`.

The plan should state what will run, why it will run, what dataset version it will use, which tools are required, what artifacts are expected, what budget it will consume, and what outcome would confirm or weaken the hypothesis.

---

### Tool Runs Are Bounded

Every experiment should be composed of approved tool runs.

A tool run should have a clear input contract, output contract, runtime backend, status, artifact outputs, and failure behavior.

The experiment system should not rely on ad hoc scripts that produce unstructured outputs.

---

### Results Must Be Traceable

Every result must trace back to:

```text
project_id
dataset_version
experiment_plan
tool_version
execution_backend
environment
parameters
random_seed
artifacts
metrics
```

Without traceability, LASI cannot tell whether improvement came from the model, the dataset, the split, the environment, or the evaluation policy.

---

### Experiments Should Be Reproducible Enough

Perfect reproducibility may not always be possible, especially with GPU training, nondeterministic kernels, remote execution, or stochastic algorithms.

LASI should still preserve enough information to rerun or audit the experiment: code version, config, dataset version, seed, tool version, dependency snapshot, host profile, command, and artifacts.

---

## Experiment Types

LASI should support multiple experiment types. The MVP only needs a small subset, but the system should use a taxonomy that can expand later.

### Baseline Probe

A baseline probe establishes initial performance and failure behavior.

Baseline probes are not meant to be final optimized models. They are used to understand the problem.

Examples:

```text
engineered-feature classifier
small neural network
PointNet-style model
linear classifier on embeddings
simple clustering analysis
```

### Confirmation Probe

A confirmation probe tests whether a historically successful approach works on a new similar dataset.

Example:

```text
Prior similar datasets performed best with PointNet + engineered arc features.
Run that combination first on this dataset.
```

If it works, the similarity prior is strengthened.

If it fails, the mismatch becomes diagnostic evidence.

### Scaling Test

A scaling test asks whether more of something helps.

Examples:

```text
more data
larger model
longer training
higher resolution
more features
stronger augmentation
```

Scaling tests help distinguish data-limited, capacity-limited, and representation-limited regimes.

### Learning Curve Experiment

A learning curve experiment evaluates performance across dataset sizes or training progress.

It helps answer whether additional data or training is likely to improve performance.

### Ablation Experiment

An ablation experiment removes or changes one component to estimate its contribution.

Examples:

```text
remove engineered size features
remove curvature features
remove augmentation
compare with and without metadata
compare model with and without pretrained embeddings
```

Ablation is useful only when the rest of the experiment is controlled.

### Error Analysis Experiment

An error analysis experiment investigates failure patterns.

It may identify confusion pairs, low-confidence borderline samples, high-confidence wrong samples, cluster-specific failures, or data regions with poor recall.

### Embedding and Cluster Experiment

An embedding and cluster experiment generates representations and analyzes natural groupings.

It helps identify class overlap, hidden subclasses, ambiguous regions, outliers, and underrepresented clusters.

### Calibration Experiment

A calibration experiment determines whether model confidence is reliable.

This matters when confidence is used for human review queues, escalation decisions, or thresholding.

### Thresholding Experiment

A thresholding experiment studies tradeoffs between false positives and false negatives.

It is especially important when the operational cost of errors is asymmetric.

### Dataset Update Validation Experiment

A dataset update validation experiment checks whether a dataset improvement proposal had the expected effect.

Example:

```text
The agent recommended adding short-arc examples.
After v0.3.0 was created, rerun the prior best model and check whether short-arc recall improved.
```

### Human Review Preparation Experiment

This experiment creates review candidates for humans.

It may produce borderline samples, low-purity cluster representatives, suspected label errors, or class-policy examples.

---

## Experiment Plan

An `ExperimentPlan` is the bridge between recommendation and execution.

The scientist provider may recommend an action. The local agent or fixed workflow compiles that recommendation into an experiment plan.

An experiment plan should include:

```text
experiment_plan_id
project_id
dataset_version
hypothesis
reason_for_experiment
experiment_type
planned_tool_runs
execution_backend
expected_artifacts
expected_signal
success_criteria
failure_criteria
budget_estimate
privacy_mode
approval_required
decision_record_required
stop_condition
handoff_after_decision
created_by
created_at
provenance
```

The plan should be recorded before tools run.

This prevents LASI from losing the reason behind an experiment.

## Component Experiment Specifications

For reusable execution, LASI separates the governed `ExperimentPlan` from an
immutable `ExperimentSpec`. The plan records why a run is proposed and is the
object authorized by the decision system. The specification records exactly
what trusted components will execute: a version-pinned component graph,
component parameters, typed artifact edges, modality, problem type, dataset
version, seed, evaluation policy, and backend.

`services.components.ExperimentSpecResolver` validates every node against the
explicit component registry, resolves Pydantic defaults, checks output-to-input
artifact compatibility, and emits a canonical JSON representation with a stable
hash. A component-pipeline plan embeds that hash. The runner rejects any
resolved specification whose hash does not match its allowed plan.

Configuration may be encoded as YAML or JSON for human and agent interaction,
but Pydantic contracts and the resolved JSON snapshot are authoritative. ICM
may contain a readable `config.yaml` copy for an experiment; it is not the
execution authority, numerical result store, or source of permission.

The component graph expresses known, bounded execution. LASI orchestration
continues to decide whether another experiment, branch, loop, review, or novel
implementation is appropriate after evidence is available.

For protected benchmarks, a component graph additionally requires the
fail-closed protected-component backend. Before invoking a handler it verifies
the statically registered handler's immutable source hash, validates every
declared input and node work directory against profile allowlists, installs
scoped audit enforcement for file, network, and subprocess events, and applies
bounded CPU, wall-time, and address-space limits. A declarative profile or an
in-process component alone is not containment evidence.

---

## Hypothesis and Expected Signal

Every experiment should have a hypothesis or research question.

Bad:

```text
Train a bigger model.
```

Better:

```text
Hypothesis:
The current model is capacity-limited.

Expected Signal:
A larger model should improve both training and validation performance, not merely reduce training loss.

Contradictory Signal:
A larger model improves training loss but validation performance remains flat or worsens.
```

This structure makes experiment results interpretable.

---

## Experiment Plan Compiler

The experiment plan compiler converts recommendations into executable plans.

Inputs:

```text
scientist_review
current_project_state
tool_registry
dataset_version
evaluation_policy
privacy_policy
budget
available_execution_backends
prior_memory
```

Outputs:

```text
experiment_plan
required_approvals
estimated_cost
expected_artifacts
blocked_reasons
```

The compiler should not blindly accept recommendations.

If the scientist provider recommends an unavailable tool, a forbidden data transfer, an over-budget run, or a duplicate experiment, the plan compiler should mark the plan as blocked or require approval.

---

## Tool Runs

A tool run is a concrete unit of execution inside an experiment.

Examples:

```text
run_dataset_characterization
train_baseline_model
generate_embeddings
run_hdbscan_clustering
compute_learning_curve
build_error_buckets
render_static_report
```

A tool run should record:

```text
tool_name
tool_version
input_refs
output_refs
parameters
execution_backend
status
start_time
end_time
runtime
warnings
errors
artifact_refs
mlflow_run_id
```

Tool runs should return structured results, not just logs.

---

## Run States

A tool run may move through:

```text
planned → staged → running → retrieving_artifacts → succeeded
```

Alternative states include:

```text
partial_success
failed
skipped
blocked
cancelled
timed_out
```

For local-only execution, `staged` and `retrieving_artifacts` may be skipped.

For SSH-backed execution, staging and artifact retrieval are important first-class states. A remote job can fail before training starts, during execution, or after training succeeds but before artifacts are retrieved.

---

## Execution Backends

LASI should support multiple execution backends.

### Local Execution

Local execution runs on the same machine as the orchestrator.

It is useful for validation, small characterization jobs, small classical models, report generation, and tests.

### SSH Remote Execution

SSH remote execution runs on a configured remote host.

The local machine remains the orchestrator and source of truth.

The remote host executes commands and returns artifacts.

SSH execution is important because the local computer may not have sufficient CPU, GPU, memory, or storage for training.

### Future Execution Backends

Future backends may include cloud batch jobs, Kubernetes, Slurm, Ray, managed Vertex jobs, or other compute systems.

These should be added only after the local and SSH execution contracts are stable.

---

## Remote Execution Requirements

Remote experiments should be auditable.

A remote run should record:

```text
host_profile
remote_workspace
staged_inputs
command
environment_setup
start_time
end_time
exit_code
logs
retrieved_artifacts
missing_artifacts
cleanup_status
```

The MVP can use SSH plus `rsync` or `scp`.

The harness should stage a run bundle, execute a deterministic command, retrieve artifacts, and then log the result locally.

Remote workers should not become independent sources of truth.

---

## Artifact Expectations

Every experiment plan should define expected artifacts.

Examples:

```text
metrics.json
predictions.parquet
model.pt
confusion_matrix.png
learning_curve.png
embeddings.parquet
clusters.parquet
error_buckets.json
run_log.txt
environment.json
```

If expected artifacts are missing, the run may be failed or partial-success depending on severity.

Artifact expectations are important because an experiment can appear to run successfully while failing to produce the evidence needed for diagnosis.

---

## Metrics and Evaluation

The experiment system should not decide metric meaning by itself. It should use the project evaluation policy.

The evaluation policy defines primary metric, secondary metrics, threshold policy, class weighting, false-positive and false-negative cost assumptions, confidence interval requirements, calibration requirements, and minimum meaningful improvement.

An experiment result should report metrics in the context of this policy.

For example, an experiment may improve overall F1 while worsening short-arc recall. Whether that is acceptable depends on the evaluation policy.

---

## Result Comparison

LASI should compare experiment results carefully.

A comparison is valid only when dataset versions, splits, label policies, evaluation policies, and metrics are comparable.

If the dataset changed in a non-comparable way, the report should say so explicitly.

Possible comparison statuses:

```text
directly_comparable
partially_comparable
not_comparable
unknown
```

The experiment system should not claim improvement when the underlying task changed.

---

## Reproducibility Records

Each experiment should preserve enough information for audit or rerun.

Minimum reproducibility record:

```text
project_id
experiment_id
dataset_version
manifest_hash
config_hash
tool_versions
code_version
random_seed
execution_backend
host_profile
environment_snapshot
command
artifact_refs
```

For neural network training, exact bitwise reproducibility may not be guaranteed. The record should still be sufficient to understand what was run.

---

## Failure Handling

Failures should be structured.

A failed experiment should record whether the failure came from:

```text
invalid_input
missing_data
tool_error
remote_execution_error
environment_error
timeout
missing_artifact
evaluation_error
privacy_block
budget_block
approval_block
unknown_error
```

Failed experiments are still useful evidence.

A tool that repeatedly fails on similar datasets may indicate a toolbox problem.

A training failure due to memory limits may influence future budget and execution planning.

A clustering failure may indicate that the representation is poor or that the tool assumptions were not met.

Failures should not be silently discarded.

---

## Partial Success

Partial success should be allowed but explicit.

An experiment may complete training but fail to generate all plots. Or it may produce metrics but fail to retrieve model files. Or a characterization job may produce distributions but fail clustering.

Partial success should include:

```text
what_succeeded
what_failed
missing_artifacts
diagnostic_impact
can_continue
```

The decision system should determine whether the project can proceed with partial evidence.

---

## Budget and Cost Awareness

Experiments consume resources.

The experiment plan should estimate cost before execution where possible.

Cost may include:

```text
wall_time
gpu_hours
cpu_hours
memory_requirement
storage_requirement
remote_transfer_size
dollar_cost
experiment_count
human_review_time
```

The decision system should block or escalate experiments that exceed budget.

For early LASI, cost estimates may be rough. They should become better as the system records actual runtime history.

---

## Experiment Results and Scientist Review

The experiment system prepares structured evidence for the scientist provider.

The scientist provider should receive a diagnostic packet, not raw unstructured logs.

The packet may include:

```text
experiment summary
dataset characterization summary
model comparison table
learning curve summary
error analysis
cluster analysis
calibration summary
artifact references
relevant knowledge context
open questions
```

The scientist provider interprets evidence and recommends next actions.

The experiment system does not treat the recommendation as execution authority. The decision system and experiment planner still mediate action.

---

## Experiment Results and Knowledge Layer

Experiment results may produce lessons, but not every result should become institutional knowledge.

The database records the result.

MLflow stores the artifacts.

The knowledge curator may draft a lesson.

Humans approve the lesson.

Example:

```text
Operational result:
PointNet + engineered arc features improved short-arc recall on scratch_pointcloud:v0.3.0.

Possible lesson:
For point-cloud scratch datasets with sparse short-arc clusters, engineered arc features may improve recall.

Knowledge status:
hypothesis or tentative lesson until supported by multiple projects.
```

This prevents one-off findings from becoming false general rules.

---

## Experiment System Data Flow

A normal experiment flow is:

```text
Project state is loaded
↓
Dataset version is selected
↓
Experiment question is defined
↓
Experiment plan is created
↓
Decision system checks whether it may run
↓
Tool runs are staged
↓
Execution occurs locally or remotely
↓
Artifacts are retrieved
↓
Metrics and outputs are logged
↓
Results are compared to expectations
↓
Diagnostic packet is updated
↓
Scientist review may be requested
↓
Report is generated or updated
↓
Outcome or next action is recorded
```

---

## MVP Experiment Scope

The MVP experiment system should support a narrow set of experiment types:

```text
baseline_probe
learning_curve
embedding_or_cluster_analysis
error_analysis
static_report_generation
```

It should support local execution and simple SSH execution.

It should log to SQLite and MLflow.

It should produce structured outputs usable by the report generator and scientist provider.

It does not need full hyperparameter optimization, neural architecture search, distributed training, cloud batch integration, or automatic retraining.

---

## Plan-Following and Diagnostic Review

An active `ResearchAction` is the executable interpretation of the current
research agenda. When it requires execution, it names an `ExperimentPlan`; the
plan and an allowing `DecisionRecord` must exist in operational memory before
the runner accepts the transition. A Markdown plan without those records is an
incomplete projection and cannot authorize work.

After a meaningful objective improvement, `ResearchLoopController` routes to
`review`. The next action must be error analysis, evidence review, or scientist
review. This prevents a metric improvement from immediately spawning a new
component without diagnosing the remaining error.

The built-in `error_analysis` capability consumes row-level actual/prediction
CSV data and emits deterministic RMSLE evidence for zero/positive target
regimes, requested segments, worst rows, and an optional baseline comparator.
`ToolSpec.capability_state` distinguishes production, experimental, stub, and
unavailable implementations. Stub and unavailable tools are rejected by the
local runner rather than returning success-shaped references.

## Unsettled Questions

The first unsettled question is how much experiment planning should be deterministic versus model-assisted. The safest starting point is deterministic plan compilation from a small set of allowed experiment types.

The second unsettled question is what counts as a successful experiment. Some experiments improve metrics, while others are successful because they reveal that model work is not the bottleneck.

The third unsettled question is how precise cost estimation needs to be in the MVP. Rough estimates may be enough at first.

The fourth unsettled question is how much failure recovery should exist for SSH jobs. The MVP can fail cleanly and record the error; later versions may resume or retry.

The fifth unsettled question is how much hyperparameter tuning belongs in LASI. Early LASI should focus on diagnosis, not exhaustive optimization.

The sixth unsettled question is whether experiment workers should be packaged as Python service functions, OpenCode-invoked commands, containers, or all three. The simplest starting point is reusable Python service functions invoked by bounded OpenCode skills and commands; generated execution commands remain recorded tool-run details.

---

## Out of Scope for This File

This file does not define dataset storage formats, database schemas, scientist-provider prompt text, report HTML templates, lifecycle governance, or model-specific implementation code.

Those belong in separate LASI documents.

This file defines how LASI thinks about experiments as controlled evidence-generating actions.
