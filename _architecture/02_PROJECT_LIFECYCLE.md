# 02_PROJECT_LIFECYCLE.md

Workflow packages define lifecycle routing as typed nodes. Conditional nodes may be
skipped only with a recorded reason; required report and outcome nodes remain reachable
when optional research is blocked or unavailable.

## Purpose

This document defines how a LASI project moves from creation to closure.

It defines project states, allowed transitions, lifecycle responsibilities, stopping conditions, and outcome recording.

It does not define database schemas, report templates, model metrics, or tool implementation details.

## Core Idea

A LASI project is not complete when experiments finish.

A project is complete when the outcome is recorded.

The outcome may be deployment, cancellation, failed validation, production failure, successful production use, research-only closure, or blocked status.

## Assignment Runtime Lifecycle

Project outcome and autonomous-assignment runtime state are separate. Runtime assignments use explicit `active`, `waiting`, `pausing`, `paused`, `escalated`, `runtime_blocked`, `cancelling`, `cancelled`, `completed`, and `failed` states. `runtime_blocked` is a deterministic local-infrastructure condition, such as a missing or unusable OpenCode CLI. It does not consume coordinator turns or retry patience and may be resumed after preflight succeeds. `pausing` and `cancelling` mean the current atomic coordinator turn must checkpoint before the requested state is final. A computer should be shut down only after `paused` or a terminal state is persisted. Resume launches a new worker from SQLite state and append-only assignment events; it never depends on conversation history.

Entering `escalated` also publishes a durable OpenCode UI notification. The UI shows a warning and pre-fills the pending question plus matching `/lasi-feedback` syntax. Restarting OpenCode replays unanswered notifications. Recording matching feedback clears the notification and resumes the assignment.

Each assignment starts with a durable `research_planning` action. A coordinator
turn may remain on that action, complete it and nominate one next action, wait
for already-running work, or reach a governed terminal state. It may not skip to
an unrelated action. Invalid directives are recorded as coordinator errors and
retried within the existing bounded error policy.

The semantic runtime represents this lifecycle as a task DAG. Tasks move through
`proposed`, `validated`, `ready`, `leased`, `running`, `result_received`, and
runtime-accepted `succeeded`, `failed`, or `blocked` states. Each attempt records
queue order, start and finish times, duration, context snapshot, rubric results,
artifacts, and token-receipt coverage. Dependency completion releases the next
task; a failed dependency blocks descendants and routes the closed frontier back
to planning instead of losing the episode.

## Project Lifecycle

created
→ dataset_validated
→ characterized
→ baseline_complete
→ scientist_reviewed
→ decision_made
→ report_generated
→ outcome_recorded
→ knowledge_curated
→ closed
