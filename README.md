# LASI

Learning as a Service is an industrial ML research harness for identifying what limits performance, preserving evidence, and guiding human decisions.

## Current State

This repository contains the architecture, governance, OpenCode operating surface, and executable Python services for durable research assignments. A persistent administrator starts a detached `ProjectRunner`; the runner repeatedly invokes fresh internal coordinator turns, checkpoints every directive and event in SQLite, and continues until completion, cancellation, a governed plateau, or a genuine escalation.

## Local challenge benchmark harness

Express challenge work as an objective through `/lasi-start`; there is no direct challenge command in the supported user surface. `ChallengeSpec` remains strict and rejects unknown fields; target, identifier, split, metric, and submission assumptions are never inferred from challenge names. File inventory and hashes precede leakage auditing, characterization, planning, decision, exact tool execution, prediction/submission validation, hidden evaluation, reporting, outcome recording, and a draft knowledge proposal.

Benchmark isolation defaults to no network, no external scientist provider, no remote execution, no arbitrary subprocess, and no hidden-label access from model-building tools. Unsupported or unsafe formats fail explicitly. The executable baseline is deterministic tabular classification/regression; other modalities currently have metadata inspection adapters only.

### Setup and limitations

Install the project with `py -3.14 -m pip install -e ".[dev]"` (or the equivalent supported Python environment), then run `py -3.14 -m pytest -q`, Ruff, and mypy. Run `alembic upgrade head` before using a fresh operational database. The challenge workspace separates `input`, `working`, `artifacts`, `submission`, `private_evaluation`, and `logs`; hidden labels belong only in the evaluator boundary. CSV, TSV, JSON, JSONL, YAML, Parquet/Arrow metadata, NumPy metadata, common image/audio/video metadata, and ZIP/TAR safety checks are supported. Excel, DICOM, NIfTI, HDF5, sparse-matrix loading, and media decoding are explicit future adapters rather than silently guessed behavior. There is no Kaggle API, scraping, leaderboard lookup, or automatic ingestion.

The detached runner invokes the documented `opencode run` interface. The `opencode` executable must be on the worker's `PATH`; set `LASI_OPENCODE_EXECUTABLE` to its absolute path when needed.

`/lasi-start` and `/lasi-resume` preflight that interface before changing assignment state. If the runtime later becomes unavailable, the worker records one `runtime_blocked` state instead of exhausting coordinator retries. Correct the reported infrastructure problem and use `/lasi-resume`.

OpenCode configuration and procedure changes are loaded at startup. Quit and restart OpenCode after changing `opencode.json`, `.opencode/command/`, `.opencode/agent/`, or `.opencode/skills/`.

## Setup

1. Open the repository in OpenCode.
2. Keep `opencode.json` as the repository configuration. It selects `lasi-admin`; the internal `lasi-coordinator` is not a user-facing agent.
3. Start and control work only with the seven commands in the Command Guide below.
4. Read the relevant `_architecture/` system document and `_workflows/` workflow before changing behavior.

## Durable Assignment Workflow

Use `/lasi-start <project ID and objective>` as the only research entry point. The administrator records the assignment and launches a detached worker; it does not do research in the interactive OpenCode turn.

1. The `ProjectRunner` invokes `lasi-coordinator` with the typed assignment and recent durable events.
2. `dataset-engineer` runs `dataset-intake` and `dataset-characterization`. It validates files, labels, splits, checksums, lineage, and comparability without changing authoritative data.
3. Obtain the durable approval required for dataset-version creation. A dataset version must not be created from a recommendation alone.
4. `experiment-engineer` runs `experiment-planning` and creates an ordered `ExperimentPlan` with exact tool IDs, dataset version, metrics, budget, expected artifacts, and stop conditions.
5. `scientist-reviewer` runs `scientist-review` after diagnostic evidence exists. The result is a `ScientistReview`, not permission to execute.
6. `governance-reviewer` runs `decision-review`. Only `allow` or `allow_with_warning` permits an approved run; `block`, `defer`, `stop_project`, `request_clarification`, and escalation stop execution.
7. `experiment-engineer` or `remote-execution-engineer` executes the exact approved tool run. Local and remote runners require the matching plan and decision; remote work also requires host trust and transfer approval.
8. `scientist-reviewer` reviews the resulting `DiagnosticPacket`. Any next action becomes a new plan and post-review decision; it is never executed directly from provider output.
9. `report-outcome-engineer` runs `report-generation` and creates the immutable fixed-template HTML report with evidence, recommendation, decision, provenance, and missing states.
10. `report-outcome-engineer` runs `outcome-recording`. Record validation, deployment, and production outcomes separately; do not call validation success production success.
11. `knowledge-curator` runs `knowledge-curation` and drafts a proposal from the report, outcome, and artifacts. Humans approve governed knowledge changes.

After each turn, the coordinator emits a typed directive: `continue`, `wait`, `complete`, or `escalate`. The runner immediately schedules the next turn for `continue`, wakes after durable external work for `wait`, and stops only at a terminal state or true human-discretion escalation. A pause or cancellation request is honored at the next atomic-turn checkpoint.

The MVP vertical slice is implemented by `services.workflows.diagnostic` and persists approvals, dataset versions, characterizations, plans, decisions, tool runs, artifacts, reviews, reports, outcome events, and knowledge proposals in their proper stores.

## Component-driven experiments

Known execution capabilities are available as explicitly registered, versioned
components. An `ExperimentSpec` declares a typed component graph; its canonical
resolved JSON is hash-bound to a governed `ExperimentPlan` before execution.
The local graph runner validates component schemas and artifact edges, creates
per-component structured results, and can log immutable output artifacts.

The included naive Titanic demonstration is intentionally a baseline, not a
claimed competitive result. After obtaining `train.csv` and `test.csv` locally,
run:

```bash
.venv/bin/python scripts/run_titanic_component_demo.py \
  --train /path/to/train.csv --test /path/to/test.csv --output /tmp/lasi-titanic
```

It performs no Kaggle submission, external provider call, or hidden-label
access. It enforces the benchmark isolation profile, produces a resolved spec,
MLflow-style immutable artifacts, a project ICM record, validation metrics, and
a format-validated 418-row `submission.csv`.

## Agent Guide

| Agent | Use it for |
|---|---|
| `lasi-admin` | Sole user-facing agent; start, inspect, pause, resume, cancel, answer escalations, and retrieve reports. |
| `lasi-coordinator` | Internal only; one ephemeral research turn invoked by `ProjectRunner`. |
| `dataset-engineer` | Dataset intake, validation, characterization, versioning, lineage, comparability, and benchmark protection. |
| `experiment-engineer` | Experiment plans, reproducibility, duplicate checks, diagnostic packets, and approved tool-run preparation. |
| `scientist-reviewer` | Provider-neutral interpretation of diagnostic evidence and recommendations. It cannot execute or authorize. |
| `governance-reviewer` | Privacy, budget, policy, risk, approval, escalation, block, and stop decisions. It does not execute. |
| `remote-execution-engineer` | Approved remote runs, host checks, staging, logs, artifacts, cleanup, and local-authority reconciliation. |
| `report-outcome-engineer` | Fixed static reports and project outcome events. |
| `knowledge-curator` | Draft lessons, hypotheses, literature notes, and knowledge proposals. It cannot approve them. |
| `contract-architect` | Review or propose typed contracts, schema versions, provenance, and boundary changes. |
| `lasi-code-reviewer` | Read-only review for authority violations, provenance gaps, contract drift, security, and missing tests. |

## Command Guide

| Command | Primary agent | Use it for |
|---|---|---|
| `/lasi-start` | `lasi-admin` | Create a durable assignment and launch its worker. |
| `/lasi-status` | `lasi-admin` | Read state, progress, wake time, and pending escalation. |
| `/lasi-pause` | `lasi-admin` | Request a checkpointed pause before shutdown. |
| `/lasi-resume` | `lasi-admin` | Resume durable work in a new detached worker. |
| `/lasi-cancel` | `lasi-admin` | Stop future work while preserving history and artifacts. |
| `/lasi-feedback` | `lasi-admin` | Record feedback for the matching escalation and resume. |
| `/lasi-report` | `lasi-admin` | Retrieve the latest governed static report without changing work. |

Use `/lasi-feedback <project-or-assignment> <escalation-id> <feedback>` when `/lasi-status` reports a pending escalation. Wait for `/lasi-status` to report `paused` before shutting down. `pausing` means the current atomic coordinator turn is still checkpointing. Cancellation never deletes assignment history.

When an assignment escalates, the runner writes a durable pending-notification artifact. The project OpenCode plugin shows a warning toast and appends the exact question and ready-to-edit `/lasi-feedback` command to the active OpenCode prompt. The notification remains pending across OpenCode restarts and is removed only after matching feedback is recorded.

## What To Provide

Include these facts in the first request whenever possible:

- Project ID and objective
- Dataset path or existing manifest
- Problem type and modality
- Target metric and evaluation policy
- Privacy mode and whether raw data may leave the local machine
- Compute or budget limits
- Existing dataset version, approval, decision, or artifact IDs
- Whether the request is intake, diagnosis, update validation, review, reporting, or outcome recording

If a required fact is missing, the correct behavior is to ask for clarification or record a blocked/deferred state, not to guess.

## Operating Principles

- Evidence comes before opinion and recommendation.
- Recommendations are not commands. A scientist provider recommends; the decision system authorizes.
- OpenCode commands, agents, and skills are the operating surface. Reusable Python services are the implementation layer.
- Experiments require a plan and decision gate before execution.
- Datasets are framework-neutral, versioned assets with lineage and explicit comparability.
- The local harness remains authoritative when work runs remotely.
- Reports are fixed static artifacts generated from structured data.
- Knowledge changes are proposed before approval.
- High-consequence actions require human approval.
- Outcomes distinguish validation success from production success.

## Repository Map

- `AGENTS.md`: repository-wide rules for agents.
- `_architecture/`: subsystem architecture and boundaries.
- `_core/`: mission, glossary, principles, and authority boundaries.
- `_workflows/`: ordered workflow specifications and handoffs.
- `.opencode/`: OpenCode commands, specialist agents, and skills.
- `.opencode/skills/`: all canonical OpenCode-discovered skill procedures, contracts, checklists, examples, and workflow-authoring guidance.
- `services/`: reusable Python implementation services and typed contracts.
- `tests/`: unit and fixture integration coverage for the current service layer.
- `REPOSITORY_GAP_ANALYSIS.md`: current maturity, gaps, and implementation sequence.

## Authority Boundary

Do not let an OpenCode command, agent, skill, or provider bypass dataset ownership, experiment planning, decision gates, governance approval, provenance, report structure, or outcome recording. If a requested action is high-consequence or underspecified, stop and escalate or create a proposal.
