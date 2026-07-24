# LASI

Learning as a Service is an industrial ML research harness for identifying what limits performance, preserving evidence, and guiding human decisions.

## Current State

This repository contains the architecture, governance, workflow, OpenCode operating surface, and an executable Python service layer. The `src/lasi/` package includes typed contracts, configuration, dataset services, operational-memory persistence, tool registration and execution, experiment-plan compilation, decision gates, provider normalization, reports, remote-run services, knowledge retrieval, outcomes, and a durable diagnostic workflow. OpenCode commands remain bounded routing/procedure prompts; broader workflows beyond the MVP diagnostic slice are not yet general-purpose resumable runners.

## Setup

1. Open the repository in OpenCode.
2. Keep `opencode.json` as the repository configuration. It selects `lasi-coordinator`, loads the core instructions, and discovers skills under `.opencode/skills/`.
3. Start work with an existing OpenCode command under `.opencode/command/`, or ask the `lasi-coordinator` agent to route the request.
4. Read the relevant `_architecture/` system document and `_workflows/` workflow before changing behavior.

The current OpenCode commands include dataset intake and characterization, experiment planning, decision review, scientist review, reporting, outcome recording, knowledge curation, and remote execution. Commands delegate to specialist agents and canonical hyphenated skills such as `dataset-intake` and `decision-review`; they are not a competing application CLI. There is not currently one command per workflow or a workflow engine that automatically executes `_workflows/**`; coordinator and specialist prompts route requests, while reusable Python services are called only where the relevant procedure has an implementation path.

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
