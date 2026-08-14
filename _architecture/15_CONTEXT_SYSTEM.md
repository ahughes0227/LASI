# Context System

## Purpose

This document defines LASI's nested ICM-style context architecture. It owns
human- and LLM-readable semantic context, selective retrieval, project
workspaces, artifact contracts, evidence claims, invalidation, and promotion.
It does not replace the database, MLflow, telemetry, queues, graph stores,
vector stores, provider routing, orchestration, decisions, or governance.

## Layers

```text
SQL task lease + structured memory → ICM projection → AgentTask → Model
```

Structured memory is machine-native operational evidence: relational records,
metric histories, graph/vector retrieval, telemetry, and artifact identifiers.
System ICM is durable institutional operating context in `system/`. Project ICM
is isolated, human-readable semantic context in `projects/<project_id>/`. Agent
context is an ephemeral, bounded assembly for one leased task. ICM is not memory
authority: it can be regenerated without changing task state, experiment
history, or accepted knowledge.

LASI decides who acts, which model or capability is routed, which work is
authorized, when critique is required, and how failures route backward. ICM
answers what a worker needs to know for that action.

## System ICM

`system/` contains the constitution, policies, capabilities, model registry and
routing guidance, playbooks, organizational rules, and learned principles.
System context is retrieved by explicit path, capability, task keywords, and a
document budget. It is never injected wholesale.

## Project ICM

Every substantial project is isolated under:

```text
00_task/       objective, success criteria, constraints
10_context/    current state, dataset profile, domain context, prior findings
20_work/       exploration, research, features, experiments, interpretation
30_evidence/   claims, metrics, plots, comparisons, failures, promotions
40_output/     recommendation, limitations, handoff
```

Each experiment has a separate `20_work/experiments/<experiment_id>/` context
with hypothesis, config, inputs, results, artifacts, critique, and invalidation
record. Experiment metrics and produced binaries remain in structured/artifact
systems; ICM records their readable interpretation and references.

## Artifact Contracts

Every capability declares READ, DO, and WRITE paths. The context store validates
declared inputs before work and rejects writes outside the declared output set
when a contract is supplied. Durable artifacts, not conversation transcripts or
model reasoning, are the normal handoff channel.

## Evidence and Critique

Claims may be rendered as YAML records separate from their evidence references. A claim status
is `unsupported`, `weak`, `conflicting`, `supported`, `strongly_supported`, or
`invalidated`. A critic invalidation writes a failure record, marks attached
experiments invalid, recursively invalidates dependent claims, and makes the
updated state reconstructable without conversation history.

## Promotion

Project observations do not automatically become system memory. A promotion is
a durable project proposal that must meet an eligibility condition (repeated,
supported, broadly reusable, critic-reviewed, or explicitly requested) and then
receive a human `promote_project_lesson` approval. Only then may a concise
principle be written under `system/learned_principles/`. Knowledge-layer
proposals and their existing governance rules remain authoritative for Git-backed
knowledge changes.

## Reconstruction and Restart

The runtime records a `ContextSnapshotRecord` for every task attempt, including
the leased task, rubric version, required inputs, structured-memory references,
ICM role, and content hash. `ICMStore.reconstruct_project_state` remains a
human-readable projection and compatibility helper; it must not schedule work or
override SQL state. Restart reconstructs operational truth from SQLite, accepted
semantic knowledge from governed Markdown, associations from the graph
projection, and task context from the recorded snapshot references.
