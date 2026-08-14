# 09_REMOTE_EXECUTION.md
# LASI Remote Execution System

## Purpose

This document defines how LASI runs experiments on remote compute.

The remote execution system is responsible for staging jobs, validating remote environments, executing commands through SSH, capturing logs, retrieving artifacts, recording run status, and preserving local orchestration authority.

It does not define experiment planning, dataset storage, tool schemas, model training logic, or report templates in detail. Those belong in separate LASI documents.

The remote execution system answers:

> How can LASI run experiments on machines other than the local orchestrator while keeping execution traceable, reproducible, and controlled?

---

## Core Idea

The local machine is the orchestrator and source of truth.

The remote machine is an execution worker.

Remote execution exists because the local machine may not have enough CPU, GPU, memory, storage, or runtime environment support to run training and analysis jobs.

LASI should support remote execution without turning the remote host into an independent copy of the system.

The local harness owns:

```text
project state
decision records
database writes
experiment plans
tool registry
artifact registration
scientist reviews
static reports
knowledge updates
```

The remote worker executes commands and returns evidence.

---

## Design Principles

### Local Orchestrator Owns State

The local LASI instance should remain the authority for project state.

Remote workers should not independently decide what to run next.

A remote run should be launched from a local experiment plan, executed on a known host, and reconciled back into local records.

---

### Remote Runs Must Be Auditable

Every remote run should record:

```text
host profile
remote workspace
staged inputs
command executed
environment setup
start time
end time
exit code
logs
expected artifacts
retrieved artifacts
missing artifacts
cleanup status
```

A future reviewer should be able to understand what ran, where it ran, and what came back.

---

### Remote Execution Is an Execution Backend

Remote execution should be one backend behind the tool-run interface.

Downstream systems should not care whether a tool ran locally or remotely. They should receive a normal `ToolRunResult`.

This keeps the rest of LASI backend-agnostic.

---

### Keep MVP Remote Execution Simple

The MVP should use SSH plus `rsync` or `scp`.

A simple approach is:

```text
create run bundle locally
copy bundle to remote host
execute deterministic command through SSH
capture logs
retrieve expected artifacts
record result locally
```

More advanced systems such as Slurm, Kubernetes, Ray, cloud batch jobs, or managed training services can be added later if the SSH contract proves insufficient.

---

## Remote Execution Model

A remote run follows this model:

```text
Local Experiment Plan
↓
RemoteRunSpec
↓
Run Bundle
↓
SSH Host
↓
Remote Command
↓
Logs and Artifacts
↓
Local ToolRunResult
↓
Database and MLflow Registration
```

The remote host should not be treated as the source of truth. It is a worker that runs a command and produces artifacts.

---

## Host Profiles

A host profile describes a remote machine LASI may use.

A host profile should include:

```text
host_profile_id
hostname
username
ssh_port
authentication_reference
remote_workspace
environment_setup_command
python_command
hardware_summary
data_transfer_policy
trust_level
enabled
```

Credentials should not be stored directly in project configs.

Project configs should reference a host profile ID.

This prevents portable project files from leaking usernames, keys, hostnames, or internal infrastructure details.

---

## Authentication

LASI should support SSH authentication through existing secure mechanisms.

Possible approaches include:

```text
SSH agent
private key path
system SSH config
managed secrets reference
enterprise credential store
```

The MVP should prefer using the user’s existing SSH configuration or SSH agent rather than storing credentials.

Credential handling should be deliberately conservative.

---

## Remote Workspace

Each host profile should define a remote workspace.

Example:

```text
/home/user/lasi_runs/
```

Each run should create an isolated run directory.

Example:

```text
/home/user/lasi_runs/project_scratch_001/run_2026_05_29_001/
```

The run directory should contain staged inputs, config snapshots, command scripts, logs, outputs, and a manifest of expected artifacts.

The local database should record the remote workspace path for each run.

---

## Run Bundle

A run bundle is the package staged to the remote worker.

It may include:

```text
tool command script
validated config
dataset manifest or dataset reference
small input files
environment metadata
expected artifact manifest
run metadata
```

Large datasets may not always be copied for each run. The run bundle may instead reference a remote dataset cache or mounted storage path.

The MVP can start with explicit staging, but larger datasets will require caching and remote dataset registration.

---

## Dataset Staging

Dataset staging is one of the hardest remote execution problems.

Small datasets can be copied with the run bundle.

Large datasets should be staged once and reused.

Sensitive datasets may not be allowed to leave the local machine or approved storage boundary.

LASI should record whether data was:

```text
copied_with_run_bundle
referenced_from_remote_cache
referenced_from_shared_storage
not_transferred_due_to_policy
```

The decision system should treat copying raw data to a remote host as a data-transfer event.

---

## Remote Dataset Cache

A remote dataset cache may be useful after the MVP.

The cache should be keyed by dataset version and content hash.

Example:

```text
remote_cache/
└── datasets/
    └── scratch_pointcloud/
        └── v0.3.0_sha256_abc123/
```

Before staging a large dataset, LASI can check whether the remote host already has the required version.

The cache should not become a separate source of truth. It is a performance optimization.

The local dataset registry remains authoritative.

---

## Environment Validation

Before running an experiment, LASI should validate the remote environment.

Validation may check:

```text
SSH connectivity
workspace exists or can be created
Python is available
required environment activation works
required package imports succeed
GPU availability if required
disk space
write permissions
expected tool files present
MLflow connectivity if needed
```

SSH diagnostics remain a reusable service operation invoked internally by the
coordinator. They are requested as part of a durable assignment rather than
through a separate user-facing specialist command.

Example:

```bash
/lasi-start project-42 Validate approved remote host gpu_box_01 before running experiments
```

Environment validation should produce a structured result.

---

## Environment Management

The remote execution system should not assume one environment manager.

Possible environment strategies include:

```text
user-provided activation command
venv
conda
Docker
Apptainer
module load
system Python
```

The MVP should probably use a user-provided setup command.

Example:

```bash
source ~/venvs/lasi/bin/activate
```

This avoids overbuilding environment management too early.

Later versions can support containers or stricter reproducibility if needed.

---

## Remote Command Execution

Remote commands should be deterministic and recorded.

A remote command might look like:

```bash
cd /home/user/lasi_runs/project_scratch_001/run_001
source ~/venvs/lasi/bin/activate
python run_tool.py --run-spec run_spec.yaml
```

The command should be generated by LASI and recorded in the remote run record.

Command output should be captured to logs.

The exit code should be recorded.

A zero exit code does not guarantee success if expected artifacts are missing.

---

## Log Capture

LASI should capture remote logs.

At minimum, it should retrieve:

```text
stdout.log
stderr.log
run_log.txt
environment.json
```

The MVP can pull logs after completion.

Later versions may stream logs during execution.

Log streaming is useful for long-running jobs, but not required for the initial remote runner.

---

## Artifact Retrieval

Every remote run should define expected artifacts.

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
environment.json
```

After the command completes, LASI should retrieve expected artifacts from the remote workspace.

Missing artifacts should be recorded.

If critical artifacts are missing, the run should fail or become partial success.

Artifact retrieval failure is different from tool execution failure. A tool may succeed remotely but fail to return evidence to the local orchestrator.

---

## Remote Run States

A remote run may move through:

```text
planned
staging
staged
environment_checking
running
retrieving_artifacts
succeeded
partial_success
failed
timed_out
cancelled
cleanup_pending
```

These states should be recorded.

Remote execution introduces failure points that do not exist in local execution. The state model should make those failure points visible.

---

## Failure Types

Remote execution failures should be structured.

Possible failure types include:

```text
ssh_connection_failed
authentication_failed
workspace_creation_failed
staging_failed
environment_validation_failed
command_failed
timeout
remote_disk_full
gpu_unavailable
missing_expected_artifact
artifact_retrieval_failed
cleanup_failed
permission_denied
unknown_remote_error
```

A structured failure type helps future debugging and tool-usefulness tracking.

---

## Partial Success

Partial success should be allowed but explicit.

Examples:

```text
training completed but model artifact was not retrieved
metrics were retrieved but plots failed
characterization completed but clustering failed
remote command succeeded but environment snapshot is missing
```

A partial success should specify:

```text
what succeeded
what failed
what artifacts are missing
whether the result is usable
whether the project can continue
```

The decision system determines whether partial evidence is enough.

---

## Cleanup

Remote cleanup should be configurable.

Some teams may want remote run directories deleted after artifact retrieval.

Others may want them preserved for debugging.

Suggested cleanup policies:

```text
keep_all
delete_after_success
delete_after_retrieval
delete_after_n_days
manual_cleanup
```

The cleanup policy should be recorded.

A cleanup failure should not necessarily invalidate the experiment, but it should be logged.

---

## Security and Privacy

Remote execution is a data-transfer boundary.

The decision system should check whether the selected remote host is allowed to receive the required data.

The remote host should have a trust level.

Suggested trust levels:

```text
local_machine
trusted_internal
approved_remote
unapproved_remote
external_cloud
```

Sensitive data should not be staged to unapproved hosts.

The remote run record should indicate whether raw data, derived data, summaries, models, or artifacts were transferred.

---

## Relationship to Decision System

The decision system authorizes remote execution.

It should check:

```text
host profile exists
host is enabled
host trust level is sufficient
privacy policy allows transfer
budget allows run
required tool supports remote backend
dataset staging is allowed
expected artifacts are defined
```

If a recommendation requires remote execution but no approved host exists, the action should be blocked or escalated.

---

## Relationship to Dataset System

The dataset system defines canonical dataset versions.

The remote execution system stages or references those versions.

The remote runner should not create new dataset versions by itself.

If a remote job generates new data, that output should return as an artifact or dataset improvement proposal. The dataset system then decides whether it becomes a new dataset version.

---

## Relationship to Experiment System

The experiment system creates the experiment plan and tool runs.

The remote execution system executes eligible tool runs on remote hosts.

A remote run should produce a normal `ToolRunResult`.

The experiment system should not need to know SSH details beyond the execution backend and host profile.

---

## Relationship to MLflow

There are two possible MLflow patterns.

### Local Registration Pattern

The remote host returns artifacts to the local machine.

The local harness logs artifacts to MLflow.

This is the recommended MVP pattern because the local harness remains clearly authoritative.

### Direct Remote Logging Pattern

The remote host logs directly to an MLflow tracking server.

This may be useful later for large artifacts or long-running jobs.

It requires stronger environment and credential management.

The MVP should use local registration unless there is a strong reason not to.

---

## Relationship to Reports

Reports should include remote execution details when relevant.

A report may show:

```text
execution backend
host profile
remote workspace
run status
runtime
retrieved artifacts
missing artifacts
failure type
```

This helps engineers distinguish model failures from execution failures.

---

## Remote Execution Data Flow

A normal remote execution flow is:

```text
Experiment plan is approved
↓
RemoteRunSpec is created
↓
Host profile is loaded
↓
Remote environment is validated
↓
Run bundle is created
↓
Inputs are staged
↓
Remote command is executed
↓
Logs are captured
↓
Artifacts are retrieved
↓
Run result is normalized
↓
Database is updated
↓
MLflow artifacts are registered
↓
Report can reference results
```

---

## MVP Remote Execution Scope

The MVP should support:

```text
SSH host profiles
user-provided environment setup command
run bundle staging
command execution
exit-code capture
post-run log retrieval
expected artifact retrieval
structured remote run result
local MLflow artifact registration
doctor-ssh command
```

The MVP does not need:

```text
Kubernetes
Slurm
Ray
cloud batch integration
remote MLflow direct logging
automatic dataset cache
container orchestration
multi-node training
live log streaming
advanced retry/resume
role-based host permissions
```

A simple SSH backend is enough at first.

---

## Later Remote Execution Abilities

Later versions may add:

```text
remote dataset cache
live log streaming
artifact checksum validation
automatic retry policies
job cancellation
remote cleanup scheduler
container execution
Slurm backend
Kubernetes backend
cloud batch backend
direct MLflow logging
GPU resource detection
cost estimation
multi-host scheduling
```

These should be added only after the SSH contract is stable.

---

## Unsettled Questions

The first unsettled question is how remote environments should be managed. The MVP should probably use a user-provided activation command.

The second unsettled question is how large datasets should be staged. The MVP can copy small datasets, but large datasets need caching or shared storage.

The third unsettled question is whether remote workers should ever write directly to MLflow. The recommended MVP answer is no.

The fourth unsettled question is how much cleanup should be automatic. Keeping run directories helps debugging but consumes storage.

The fifth unsettled question is how to handle interrupted SSH sessions. The MVP can fail cleanly; later versions may support resume.

The sixth unsettled question is whether remote execution should support Windows hosts. The initial implementation should probably assume Linux remote workers.

The seventh unsettled question is how strict remote environment validation should be before a job is allowed to run.

---

## Out of Scope for This File

This file does not define the full remote-run database schema, SSH library implementation, container specification, cloud execution backends, experiment planning rules, or model-training code.

Those belong in separate LASI documents.

This file defines how LASI thinks about remote execution as a controlled execution backend.
