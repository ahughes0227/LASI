# LASI

Learning as a Service is an industrial ML research harness for identifying what limits performance, preserving evidence, and guiding human decisions.

## Current State

This repository contains the architecture, governance, workflow, OpenCode operating surface, and an executable Python service layer. The `src/lasi/` package includes typed contracts, configuration, dataset services, operational-memory persistence, tool registration and execution, experiment-plan compilation, decision gates, provider normalization, reports, remote-run services, knowledge retrieval, outcomes, and a durable diagnostic workflow. OpenCode commands remain bounded routing/procedure prompts; broader workflows beyond the MVP diagnostic slice are not yet general-purpose resumable runners.

## Local challenge benchmark harness

Start with `/lasi-challenge-evaluation` and supply a brief plus explicit local files. `ChallengeSpec` is strict and rejects unknown fields; target, identifier, split, metric, and submission assumptions are never inferred from challenge names. File inventory and hashes precede leakage auditing, characterization, planning, decision, exact tool execution, prediction/submission validation, hidden evaluation, reporting, outcome recording, and a draft knowledge proposal.

Benchmark isolation defaults to no network, no external scientist provider, no remote execution, no arbitrary subprocess, and no hidden-label access from model-building tools. Unsupported or unsafe formats fail explicitly. The executable baseline is deterministic tabular classification/regression; other modalities currently have metadata inspection adapters only.

### Setup and limitations

Install the project with `py -3.14 -m pip install -e ".[dev]"` (or the equivalent supported Python environment), then run `py -3.14 -m pytest -q`, Ruff, and mypy. Run `alembic upgrade head` before using a fresh operational database. The challenge workspace separates `input`, `working`, `artifacts`, `submission`, `private_evaluation`, and `logs`; hidden labels belong only in the evaluator boundary. CSV, TSV, JSON, JSONL, YAML, Parquet/Arrow metadata, NumPy metadata, common image/audio/video metadata, and ZIP/TAR safety checks are supported. Excel, DICOM, NIfTI, HDF5, sparse-matrix loading, and media decoding are explicit future adapters rather than silently guessed behavior. There is no Kaggle API, scraping, leaderboard lookup, or automatic ingestion.

OpenCode configuration and procedure changes are loaded at startup. Quit and restart OpenCode after changing `opencode.json`, `.opencode/command/`, `.opencode/agent/`, or `.opencode/skills/`.

## Setup

1. Open the repository in OpenCode.
2. Keep `opencode.json` as the repository configuration. It selects `lasi-coordinator`, loads the core instructions, and discovers skills under `.opencode/skills/`.
3. Start work with an existing OpenCode command under `.opencode/command/`, or ask the `lasi-coordinator` agent to route the request.
4. Read the relevant `_architecture/` system document and `_workflows/` workflow before changing behavior.

## Ideal Workflow

Use the coordinator as the default entry point. Do not ask every specialist to work at once and do not skip the decision handoff.

1. Start with `/lasi-dataset-diagnostic` or ask `lasi-coordinator`: “Diagnose project `<project_id>` using dataset `<path or manifest>`, target metric `<metric>`, privacy mode `<mode>`, and budget `<budget>`.”
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

The MVP vertical slice is implemented by `lasi.workflows.diagnostic` and persists approvals, dataset versions, characterizations, plans, decisions, tool runs, artifacts, reviews, reports, outcome events, and knowledge proposals in their proper stores.

## Agent Guide

| Agent | Use it for |
|---|---|
| `lasi-coordinator` | Start here; route work, enforce ordering, collect handoffs, and stop unsafe execution. |
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
| `/lasi-dataset-diagnostic` | `lasi-coordinator` | Complete dataset diagnostic workflow and handoffs. |
| `/lasi-intake` | `dataset-engineer` | Create or validate a governed dataset manifest. |
| `/lasi-characterize` | `dataset-engineer` | Produce dataset characterization evidence. |
| `/lasi-dataset-update-validation` | `dataset-engineer` | Validate a proposed parent/child dataset update. |
| `/lasi-plan` | `experiment-engineer` | Compile an evidence-backed experiment plan. |
| `/lasi-scientist-review` | `scientist-reviewer` | Analyze a diagnostic packet. |
| `/lasi-decision-review` | `governance-reviewer` | Record authorization, blocking, escalation, or proposal conversion. |
| `/lasi-remote-run` | `remote-execution-engineer` | Prepare or record an approved remote run. |
| `/lasi-report` | `report-outcome-engineer` | Generate an immutable static report. |
| `/lasi-record-outcome` | `report-outcome-engineer` | Record a governed project outcome and event history. |
| `/lasi-knowledge-proposal` | `knowledge-curator` | Draft a knowledge proposal without approving it. |
| `/lasi-sabbatical-review` | `lasi-coordinator` | Review accumulated outcomes and propose process changes. |
| `/lasi-foundation-opportunity-review` | `lasi-coordinator` | Assess reusable representation opportunities without training automatically. |

Use direct specialist commands when you are resuming one bounded step. Use `/lasi-dataset-diagnostic` for a new project or when the handoff state is unclear.

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
- `src/lasi/`: reusable Python implementation services and typed contracts.
- `tests/`: unit and fixture integration coverage for the current service layer.
- `REPOSITORY_GAP_ANALYSIS.md`: current maturity, gaps, and implementation sequence.

## Authority Boundary

Do not let an OpenCode command, agent, skill, or provider bypass dataset ownership, experiment planning, decision gates, governance approval, provenance, report structure, or outcome recording. If a requested action is high-consequence or underspecified, stop and escalate or create a proposal.
